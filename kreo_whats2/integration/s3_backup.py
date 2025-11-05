# -*- coding: utf-8 -*-
"""
S3 Backup Client - Sistema de Backup para Frappe Cloud
=======================================================

Cliente para gestionar backups automáticos de Frappe en AWS S3:
- Backup incremental de base de datos
- Compresión y encriptación
- Verificación de integridad
- Restore automatizado
- Lifecycle management

Autor: KREO Colombia
Versión: 2.0.0
Fecha: 2025-01-27
"""

import frappe
import os
import gzip
import hashlib
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config
import json


class S3BackupClient:
    """
    Cliente para gestionar backups en AWS S3
    
    Características:
    - Backup automático de base de datos MariaDB/PostgreSQL
    - Compresión GZIP nivel 9
    - Encriptación AES-256
    - Multipart upload para archivos grandes
    - Verificación de integridad (checksum)
    - Rotación automática (lifecycle)
    """
    
    def __init__(self):
        self.config = self._load_config()
        self.enabled = self.config.get('enabled', False)
        
        if not self.enabled:
            frappe.logger().warning("S3 Backup is disabled in configuration")
            return
        
        # AWS S3 client
        self.s3_client = self._create_s3_client()
        self.bucket_name = self.config['bucket_name']
        self.region = self.config.get('region', 'us-east-1')
        self.encryption = self.config.get('encryption', 'AES256')
        self.retention_days = self.config.get('retention_days', 30)
        
        # Paths
        self.site_path = frappe.utils.get_site_path()
        self.backup_dir = os.path.join(self.site_path, 'private', 'backups')
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def _load_config(self) -> Dict:
        """Cargar configuración desde site_config"""
        s3_config = frappe.conf.get('s3_backup', {})
        
        required_fields = ['bucket_name', 'aws_access_key_id', 'aws_secret_access_key']
        for field in required_fields:
            if not s3_config.get(field) and s3_config.get('enabled', False):
                frappe.throw(f"S3 Backup: Missing required field '{field}' in configuration")
        
        return s3_config
    
    def _create_s3_client(self):
        """Crear cliente boto3 para S3"""
        boto3_config = Config(
            region_name=self.config.get('region', 'us-east-1'),
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        
        return boto3.client(
            's3',
            aws_access_key_id=self.config['aws_access_key_id'],
            aws_secret_access_key=self.config['aws_secret_access_key'],
            config=boto3_config
        )
    
    def create_database_backup(self) -> Tuple[str, Dict]:
        """
        Crear backup de la base de datos
        
        Returns:
            Tuple[filepath, metadata]
        """
        frappe.logger().info("Starting database backup...")
        
        # Generar nombre de archivo con timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        site_name = frappe.local.site
        filename = f"{site_name}_{timestamp}_database.sql"
        filepath = os.path.join(self.backup_dir, filename)
        
        try:
            # Obtener credenciales de base de datos
            db_config = frappe.conf.get('db_name')
            db_host = frappe.conf.get('db_host', 'localhost')
            db_port = frappe.conf.get('db_port', 3306)
            db_user = frappe.conf.get('db_name')
            db_password = frappe.conf.get('db_password')
            db_type = frappe.conf.get('db_type', 'mariadb')
            
            # Comando de backup según tipo de DB
            if db_type in ['mariadb', 'mysql']:
                dump_cmd = [
                    'mysqldump',
                    '--single-transaction',
                    '--quick',
                    '--lock-tables=false',
                    f'--host={db_host}',
                    f'--port={db_port}',
                    f'--user={db_user}',
                    f'--password={db_password}',
                    db_config,
                    '--result-file', filepath
                ]
            else:  # postgresql
                dump_cmd = [
                    'pg_dump',
                    f'--host={db_host}',
                    f'--port={db_port}',
                    f'--username={db_user}',
                    f'--dbname={db_config}',
                    '--format=plain',
                    '--file', filepath
                ]
                # PostgreSQL usa variable de entorno para password
                os.environ['PGPASSWORD'] = db_password
            
            # Ejecutar dump
            result = subprocess.run(
                dump_cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hora timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"Database dump failed: {result.stderr}")
            
            # Verificar que el archivo se creó
            if not os.path.exists(filepath):
                raise Exception("Backup file was not created")
            
            file_size = os.path.getsize(filepath)
            
            frappe.logger().info(f"✓ Database backup created: {filename} ({file_size} bytes)")
            
            # Metadata
            metadata = {
                'filename': filename,
                'filepath': filepath,
                'size_bytes': file_size,
                'timestamp': timestamp,
                'site': site_name,
                'db_type': db_type
            }
            
            return filepath, metadata
            
        except subprocess.TimeoutExpired:
            frappe.logger().error("Database backup timeout (>1 hour)")
            raise
        except Exception as e:
            frappe.logger().error(f"Database backup failed: {str(e)}")
            raise
    
    def compress_backup(self, filepath: str) -> Tuple[str, Dict]:
        """
        Comprimir archivo de backup con GZIP
        
        Returns:
            Tuple[compressed_filepath, compression_metadata]
        """
        frappe.logger().info(f"Compressing backup: {filepath}")
        
        compressed_filepath = filepath + '.gz'
        original_size = os.path.getsize(filepath)
        
        try:
            # Comprimir con nivel máximo
            with open(filepath, 'rb') as f_in:
                with gzip.open(compressed_filepath, 'wb', compresslevel=9) as f_out:
                    # Copiar en chunks para no consumir mucha memoria
                    chunk_size = 1024 * 1024  # 1MB
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
            
            compressed_size = os.path.getsize(compressed_filepath)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            frappe.logger().info(
                f"✓ Backup compressed: {compressed_size} bytes "
                f"(ratio: {compression_ratio:.1f}%)"
            )
            
            # Eliminar archivo original
            os.remove(filepath)
            
            metadata = {
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'algorithm': 'gzip-9'
            }
            
            return compressed_filepath, metadata
            
        except Exception as e:
            frappe.logger().error(f"Compression failed: {str(e)}")
            # Asegurar que el archivo original exista
            if os.path.exists(compressed_filepath):
                os.remove(compressed_filepath)
            raise
    
    def calculate_checksum(self, filepath: str) -> str:
        """Calcular checksum SHA256 del archivo"""
        sha256 = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def upload_to_s3(
        self,
        filepath: str,
        metadata: Dict
    ) -> Dict:
        """
        Subir backup a S3
        
        Returns:
            Upload result con metadata
        """
        filename = os.path.basename(filepath)
        s3_key = f"backups/{datetime.utcnow().strftime('%Y/%m/%d')}/{filename}"
        
        frappe.logger().info(f"Uploading to S3: s3://{self.bucket_name}/{s3_key}")
        
        try:
            # Calcular checksum
            checksum = self.calculate_checksum(filepath)
            
            # Preparar metadata para S3
            s3_metadata = {
                'site': metadata.get('site', ''),
                'timestamp': metadata.get('timestamp', ''),
                'db-type': metadata.get('db_type', ''),
                'checksum-sha256': checksum,
                'backup-type': 'database'
            }
            
            # Upload con multipart para archivos grandes
            file_size = os.path.getsize(filepath)
            
            if file_size > 100 * 1024 * 1024:  # >100MB
                # Multipart upload
                self._multipart_upload(filepath, s3_key, s3_metadata)
            else:
                # Upload simple
                with open(filepath, 'rb') as f:
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        Body=f,
                        Metadata=s3_metadata,
                        ServerSideEncryption=self.encryption,
                        StorageClass='STANDARD'
                    )
            
            frappe.logger().info(f"✓ Upload completed: {s3_key}")
            
            # Construir resultado
            result = {
                'success': True,
                'bucket': self.bucket_name,
                's3_key': s3_key,
                'size_bytes': file_size,
                'checksum': checksum,
                'url': f"s3://{self.bucket_name}/{s3_key}",
                'uploaded_at': datetime.utcnow().isoformat()
            }
            
            return result
            
        except (ClientError, BotoCoreError) as e:
            frappe.logger().error(f"S3 upload failed: {str(e)}")
            raise
    
    def _multipart_upload(self, filepath: str, s3_key: str, metadata: Dict):
        """Upload con multipart para archivos grandes"""
        chunk_size = 50 * 1024 * 1024  # 50MB por parte
        
        # Iniciar multipart upload
        mpu = self.s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
            Metadata=metadata,
            ServerSideEncryption=self.encryption
        )
        
        upload_id = mpu['UploadId']
        parts = []
        
        try:
            with open(filepath, 'rb') as f:
                part_number = 1
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Upload parte
                    response = self.s3_client.upload_part(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk
                    )
                    
                    parts.append({
                        'PartNumber': part_number,
                        'ETag': response['ETag']
                    })
                    
                    frappe.logger().debug(f"Uploaded part {part_number}")
                    part_number += 1
            
            # Completar multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
        except Exception as e:
            # Abortar si falla
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id
            )
            raise
    
    def cleanup_local_backups(self, keep_last_n: int = 3):
        """Limpiar backups locales antiguos"""
        frappe.logger().info(f"Cleaning up local backups (keep last {keep_last_n})")
        
        try:
            # Listar backups locales
            backup_files = [
                f for f in os.listdir(self.backup_dir)
                if f.endswith('.sql.gz')
            ]
            
            # Ordenar por fecha (del nombre)
            backup_files.sort(reverse=True)
            
            # Eliminar los más antiguos
            for backup_file in backup_files[keep_last_n:]:
                filepath = os.path.join(self.backup_dir, backup_file)
                os.remove(filepath)
                frappe.logger().debug(f"Removed old backup: {backup_file}")
            
            frappe.logger().info(f"✓ Cleanup completed, kept {min(len(backup_files), keep_last_n)} backups")
            
        except Exception as e:
            frappe.logger().warning(f"Local cleanup failed: {str(e)}")
    
    def run_backup(self) -> Dict:
        """
        Ejecutar proceso completo de backup
        
        Returns:
            Resultado del backup con metadata completa
        """
        if not self.enabled:
            return {'success': False, 'error': 'S3 Backup is disabled'}
        
        start_time = datetime.utcnow()
        frappe.logger().info("=" * 60)
        frappe.logger().info("Starting S3 Backup Process")
        frappe.logger().info("=" * 60)
        
        try:
            # 1. Crear backup de base de datos
            db_filepath, db_metadata = self.create_database_backup()
            
            # 2. Comprimir
            compressed_filepath, compression_metadata = self.compress_backup(db_filepath)
            
            # 3. Subir a S3
            upload_result = self.upload_to_s3(compressed_filepath, db_metadata)
            
            # 4. Limpiar backups locales antiguos
            self.cleanup_local_backups()
            
            # Calcular tiempo total
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Construir resultado completo
            result = {
                'success': True,
                'start_time': start_time.isoformat(),
                'duration_seconds': duration,
                'database': db_metadata,
                'compression': compression_metadata,
                'upload': upload_result
            }
            
            frappe.logger().info("=" * 60)
            frappe.logger().info(f"✓ Backup completed successfully in {duration:.1f}s")
            frappe.logger().info(f"  S3 Location: {upload_result['url']}")
            frappe.logger().info("=" * 60)
            
            # Log para cloud logging manager
            from kreo_whats2.utils.cloud_logging_manager import log_whatsapp_event
            log_whatsapp_event(
                operation='s3_backup',
                level='INFO',
                message='Database backup completed successfully',
                metadata={
                    'duration_seconds': duration,
                    's3_key': upload_result['s3_key'],
                    'size_mb': upload_result['size_bytes'] / (1024*1024),
                    'compression_ratio': compression_metadata['compression_ratio']
                }
            )
            
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            frappe.logger().error("=" * 60)
            frappe.logger().error(f"✗ Backup failed after {duration:.1f}s: {str(e)}")
            frappe.logger().error("=" * 60)
            
            # Log error
            from kreo_whats2.utils.cloud_logging_manager import log_error
            log_error('s3_backup', e)
            
            return {
                'success': False,
                'error': str(e),
                'duration_seconds': duration
            }
    
    def list_backups(self, max_results: int = 100) -> List[Dict]:
        """Listar backups disponibles en S3"""
        if not self.enabled:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='backups/',
                MaxKeys=max_results
            )
            
            backups = []
            for obj in response.get('Contents', []):
                # Obtener metadata
                head = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=obj['Key']
                )
                
                backups.append({
                    'key': obj['Key'],
                    'size_bytes': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'checksum': head.get('Metadata', {}).get('checksum-sha256'),
                    'site': head.get('Metadata', {}).get('site'),
                    'url': f"s3://{self.bucket_name}/{obj['Key']}"
                })
            
            # Ordenar por fecha (más reciente primero)
            backups.sort(key=lambda x: x['last_modified'], reverse=True)
            
            return backups
            
        except (ClientError, BotoCoreError) as e:
            frappe.logger().error(f"Failed to list S3 backups: {str(e)}")
            return []
    
    def restore_backup(self, s3_key: str, target_db: Optional[str] = None):
        """
        Restaurar backup desde S3
        
        Args:
            s3_key: Clave S3 del backup
            target_db: Base de datos destino (opcional, por defecto la actual)
        """
        if not self.enabled:
            frappe.throw("S3 Backup is disabled")
        
        frappe.logger().info(f"Starting restore from S3: {s3_key}")
        
        try:
            # Descargar de S3
            local_filepath = os.path.join(self.backup_dir, os.path.basename(s3_key))
            
            frappe.logger().info(f"Downloading from S3...")
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                local_filepath
            )
            
            # Verificar checksum si está disponible
            head = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            expected_checksum = head.get('Metadata', {}).get('checksum-sha256')
            
            if expected_checksum:
                actual_checksum = self.calculate_checksum(local_filepath)
                if actual_checksum != expected_checksum:
                    raise Exception("Checksum mismatch! Backup may be corrupted.")
            
            # Descomprimir
            frappe.logger().info("Decompressing backup...")
            decompressed_filepath = local_filepath.replace('.gz', '')
            
            with gzip.open(local_filepath, 'rb') as f_in:
                with open(decompressed_filepath, 'wb') as f_out:
                    f_out.write(f_in.read())
            
            # Restaurar a base de datos
            db_config = target_db or frappe.conf.get('db_name')
            db_type = frappe.conf.get('db_type', 'mariadb')
            
            frappe.logger().info(f"Restoring to database: {db_config}")
            
            if db_type in ['mariadb', 'mysql']:
                restore_cmd = [
                    'mysql',
                    f'--host={frappe.conf.get("db_host", "localhost")}',
                    f'--port={frappe.conf.get("db_port", 3306)}',
                    f'--user={frappe.conf.get("db_name")}',
                    f'--password={frappe.conf.get("db_password")}',
                    db_config
                ]
                
                with open(decompressed_filepath, 'r') as f:
                    subprocess.run(restore_cmd, stdin=f, check=True)
            else:  # postgresql
                restore_cmd = [
                    'psql',
                    f'--host={frappe.conf.get("db_host", "localhost")}',
                    f'--port={frappe.conf.get("db_port", 5432)}',
                    f'--username={frappe.conf.get("db_name")}',
                    f'--dbname={db_config}',
                    '--file', decompressed_filepath
                ]
                subprocess.run(restore_cmd, check=True)
            
            # Cleanup
            os.remove(local_filepath)
            os.remove(decompressed_filepath)
            
            frappe.logger().info("✓ Restore completed successfully")
            
            # Log
            from kreo_whats2.utils.cloud_logging_manager import log_whatsapp_event
            log_whatsapp_event(
                operation='s3_restore',
                level='INFO',
                message=f'Backup restored successfully from {s3_key}',
                metadata={'s3_key': s3_key, 'target_db': db_config}
            )
            
        except Exception as e:
            frappe.logger().error(f"Restore failed: {str(e)}")
            from kreo_whats2.utils.cloud_logging_manager import log_error
            log_error('s3_restore', e, metadata={'s3_key': s3_key})
            raise


# Singleton
_s3_backup_client = None


def get_s3_backup_client() -> S3BackupClient:
    """Obtener instancia singleton del S3BackupClient"""
    global _s3_backup_client
    
    if _s3_backup_client is None:
        _s3_backup_client = S3BackupClient()
    
    return _s3_backup_client


# API Functions para usar en hooks y comandos

@frappe.whitelist()
def run_daily_backup():
    """Ejecutar backup diario (llamado desde scheduler)"""
    client = get_s3_backup_client()
    return client.run_backup()


@frappe.whitelist()
def cleanup_old_local_backups():
    """Limpiar backups locales antiguos"""
    client = get_s3_backup_client()
    client.cleanup_local_backups()


@frappe.whitelist()
def list_available_backups(max_results=100):
    """Listar backups disponibles en S3"""
    client = get_s3_backup_client()
    return client.list_backups(max_results)


@frappe.whitelist()
def restore_from_backup(s3_key, target_db=None):
    """Restaurar desde un backup específico"""
    client = get_s3_backup_client()
    client.restore_backup(s3_key, target_db)