#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Sistema de Health Checks para servicios de WhatsApp
Verifica estado de todos los servicios críticos y proporciona métricas de salud
"""

import frappe
import redis
import requests
import logging
import time
import json
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from frappe import _

from kreo_whats2.kreo_whats2.integration.redis_config import redis_manager
from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager

logger = get_logger("health_checker")

@dataclass
class HealthCheckResult:
    """Resultado de un health check"""
    service_name: str
    status: str  # 'healthy', 'unhealthy', 'degraded'
    response_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class WhatsAppHealthChecker:
    """Sistema de health checks para servicios de WhatsApp"""
    
    def __init__(self):
        self.check_results: List[HealthCheckResult] = []
        self.last_check_time = None
        self.overall_status = 'unknown'
    
    def check_redis_queue(self) -> HealthCheckResult:
        """Verificar salud de Redis Queue"""
        start_time = time.time()
        
        try:
            client = redis_manager.get_queue_client()
            if client:
                # Test ping
                client.ping()
                
                # Test conexión con timeout
                response_time = time.time() - start_time
                
                # Obtener info de Redis
                info = client.info()
                
                # Verificar métricas importantes
                memory_usage = info.get('used_memory_human', 'N/A')
                connected_clients = info.get('connected_clients', 0)
                total_commands_processed = info.get('total_commands_processed', 0)
                
                metadata = {
                    'memory_usage': memory_usage,
                    'connected_clients': connected_clients,
                    'total_commands_processed': total_commands_processed,
                    'pool_stats': redis_manager.get_pool_stats().get('queue', {})
                }
                
                # Determinar estado basado en métricas
                if connected_clients > 50:  # Umbral de alta carga
                    status = 'degraded'
                else:
                    status = 'healthy'
                
                return HealthCheckResult(
                    service_name='redis-queue',
                    status=status,
                    response_time=response_time,
                    metadata=metadata
                )
            else:
                return HealthCheckResult(
                    service_name='redis-queue',
                    status='unhealthy',
                    response_time=time.time() - start_time,
                    error_message='No se puede conectar al cliente Redis'
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='redis-queue',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error Redis: {str(e)}'
            )
    
    def check_redis_cache(self) -> HealthCheckResult:
        """Verificar salud de Redis Cache"""
        start_time = time.time()
        
        try:
            client = redis_manager.get_cache_client()
            if client:
                client.ping()
                response_time = time.time() - start_time
                
                info = client.info()
                metadata = {
                    'memory_usage': info.get('used_memory_human', 'N/A'),
                    'connected_clients': info.get('connected_clients', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                }
                
                return HealthCheckResult(
                    service_name='redis-cache',
                    status='healthy',
                    response_time=response_time,
                    metadata=metadata
                )
            else:
                return HealthCheckResult(
                    service_name='redis-cache',
                    status='unhealthy',
                    response_time=time.time() - start_time,
                    error_message='No se puede conectar al cliente Redis Cache'
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='redis-cache',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error Redis Cache: {str(e)}'
            )
    
    def check_meta_api(self) -> HealthCheckResult:
        """Verificar salud de Meta API (WhatsApp Business API)"""
        start_time = time.time()
        
        try:
            # Obtener configuración de WhatsApp
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.meta_api_url:
                return HealthCheckResult(
                    service_name='meta-api',
                    status='unhealthy',
                    response_time=time.time() - start_time,
                    error_message='URL de Meta API no configurada'
                )
            
            # Test de conectividad básica
            test_url = f"{whatsapp_settings.meta_api_url}/v1/health"
            
            response = requests.get(
                test_url,
                timeout=10,
                headers={
                    'Authorization': f'Bearer {whatsapp_settings.meta_access_token}',
                    'Content-Type': 'application/json'
                }
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                metadata = {
                    'status_code': response.status_code,
                    'response_size': len(response.content),
                    'content_type': response.headers.get('content-type', 'unknown')
                }
                
                return HealthCheckResult(
                    service_name='meta-api',
                    status='healthy',
                    response_time=response_time,
                    metadata=metadata
                )
            else:
                return HealthCheckResult(
                    service_name='meta-api',
                    status='unhealthy',
                    response_time=response_time,
                    error_message=f'Status {response.status_code}: {response.text}'
                )
                
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='meta-api',
                status='unhealthy',
                response_time=response_time,
                error_message='Timeout al conectar con Meta API'
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='meta-api',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error Meta API: {str(e)}'
            )
    
    def check_ngrok_tunnel(self) -> HealthCheckResult:
        """Verificar salud del túnel Ngrok"""
        start_time = time.time()
        
        try:
            # Verificar si Ngrok está corriendo y tiene túneles activos
            import subprocess
            import sys
            
            try:
                if sys.platform == "win32":
                    result = subprocess.run(
                        ['ngrok', 'tunnels', '--format', 'json'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                else:
                    result = subprocess.run(
                        ['ngrok', 'tunnels', '--format', 'json'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                
                response_time = time.time() - start_time
                
                if result.returncode == 0:
                    try:
                        tunnels_data = json.loads(result.stdout)
                        tunnel_count = len(tunnels_data.get('tunnels', []))
                        
                        metadata = {
                            'tunnel_count': tunnel_count,
                            'tunnels': tunnels_data.get('tunnels', [])
                        }
                        
                        if tunnel_count > 0:
                            return HealthCheckResult(
                                service_name='ngrok-tunnel',
                                status='healthy',
                                response_time=response_time,
                                metadata=metadata
                            )
                        else:
                            return HealthCheckResult(
                                service_name='ngrok-tunnel',
                                status='degraded',
                                response_time=response_time,
                                error_message='No hay túneles activos'
                            )
                            
                    except json.JSONDecodeError:
                        return HealthCheckResult(
                            service_name='ngrok-tunnel',
                            status='unhealthy',
                            response_time=response_time,
                            error_message='Respuesta JSON inválida de Ngrok'
                        )
                else:
                    return HealthCheckResult(
                        service_name='ngrok-tunnel',
                        status='unhealthy',
                        response_time=response_time,
                        error_message=f'Error Ngrok: {result.stderr}'
                    )
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                response_time = time.time() - start_time
                return HealthCheckResult(
                    service_name='ngrok-tunnel',
                    status='unhealthy',
                    response_time=response_time,
                    error_message='Ngrok no disponible o timeout'
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='ngrok-tunnel',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error Ngrok: {str(e)}'
            )
    
    def check_database_connection(self) -> HealthCheckResult:
        """Verificar conexión a base de datos"""
        start_time = time.time()
        
        try:
            # Testear conexión a Frappe DB
            if frappe.db:
                frappe.db.sql("SELECT 1")
                response_time = time.time() - start_time
                
                # Obtener estadísticas básicas
                table_count = frappe.db.sql("SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = DATABASE()", as_dict=True)
                
                metadata = {
                    'table_count': table_count[0].get('count', 0) if table_count else 0,
                    'connection_status': 'active'
                }
                
                return HealthCheckResult(
                    service_name='database',
                    status='healthy',
                    response_time=response_time,
                    metadata=metadata
                )
            else:
                return HealthCheckResult(
                    service_name='database',
                    status='unhealthy',
                    response_time=time.time() - start_time,
                    error_message='No hay conexión a base de datos'
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='database',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error DB: {str(e)}'
            )
    
    def check_webhook_endpoint(self) -> HealthCheckResult:
        """Verificar endpoint de webhook"""
        start_time = time.time()
        
        try:
            # Testear endpoint de webhook local
            response = requests.get(
                'http://localhost:3000/health',
                timeout=5
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                metadata = {
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'content': response.text[:100]  # Primeros 100 caracteres
                }
                
                return HealthCheckResult(
                    service_name='webhook-endpoint',
                    status='healthy',
                    response_time=response_time,
                    metadata=metadata
                )
            else:
                return HealthCheckResult(
                    service_name='webhook-endpoint',
                    status='unhealthy',
                    response_time=response_time,
                    error_message=f'Status {response.status_code}'
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name='webhook-endpoint',
                status='unhealthy',
                response_time=response_time,
                error_message=f'Error webhook: {str(e)}'
            )
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Ejecutar todos los health checks con logging estructurado avanzado"""
        # Iniciar contexto de operación para seguimiento de performance
        correlation_id = logging_manager.start_operation_context(
            "health_check_execution",
            metadata={"check_type": "comprehensive", "timestamp": time.time()}
        )
        
        self.check_results = []
        self.last_check_time = datetime.now()
        
        # Logging de inicio de health checks
        log_event(
            "health_checker",
            "INFO",
            "Iniciando ejecución de health checks",
            operation="health_check_start",
            performance_metrics={
                "total_checks": 6,
                "execution_timestamp": time.time()
            },
            business_metrics={
                "system_monitoring_active": True
            },
            metadata={
                "component": "health_check_execution",
                "correlation_id": correlation_id
            }
        )
        
        # Ejecutar checks en paralelo para mejor performance
        import concurrent.futures
        
        checks = [
            ('redis-queue', self.check_redis_queue),
            ('redis-cache', self.check_redis_cache),
            ('meta-api', self.check_meta_api),
            ('ngrok-tunnel', self.check_ngrok_tunnel),
            ('database', self.check_database_connection),
            ('webhook-endpoint', self.check_webhook_endpoint)
        ]
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_to_check = {executor.submit(check_func): name for name, check_func in checks}
            
            for future in concurrent.futures.as_completed(future_to_check):
                check_name = future_to_check[future]
                try:
                    result = future.result()
                    self.check_results.append(result)
                except Exception as e:
                    logger.error(f"Error en health check {check_name}: {str(e)}")
                    log_error("health_checker", e, {
                        "operation": "health_check_execution",
                        "check_name": check_name,
                        "correlation_id": correlation_id
                    })
                    self.check_results.append(HealthCheckResult(
                        service_name=check_name,
                        status='unhealthy',
                        response_time=0,
                        error_message=f'Error ejecutando check: {str(e)}'
                    ))
        
        execution_time = time.time() - start_time
        
        # Determinar estado general
        healthy_count = sum(1 for r in self.check_results if r.status == 'healthy')
        total_count = len(self.check_results)
        
        if healthy_count == total_count:
            self.overall_status = 'healthy'
        elif healthy_count >= total_count * 0.7:  # 70% o más saludables
            self.overall_status = 'degraded'
        else:
            self.overall_status = 'unhealthy'
        
        # Registrar resultados con logging avanzado
        self._log_health_check_results()
        
        # Logging de resultados de health checks
        log_event(
            "health_checker",
            "INFO",
            f"Health checks completados - Estado: {self.overall_status}",
            operation="health_check_completion",
            performance_metrics={
                "execution_time": execution_time,
                "total_checks": total_count,
                "healthy_checks": healthy_count,
                "degraded_checks": sum(1 for r in self.check_results if r.status == 'degraded'),
                "unhealthy_checks": sum(1 for r in self.check_results if r.status == 'unhealthy')
            },
            business_metrics={
                "system_health_score": (healthy_count / total_count) * 100 if total_count > 0 else 0,
                "infrastructure_reliability": self.overall_status == 'healthy'
            },
            metadata={
                "component": "health_check_results",
                "correlation_id": correlation_id,
                "overall_status": self.overall_status
            }
        )
        
        return self._format_results()
    
    def _log_health_check_results(self):
        """Registrar resultados de health check"""
        logger.info(f"Health check completado - Estado general: {self.overall_status}")
        
        for result in self.check_results:
            if result.status == 'healthy':
                logger.info(f"✓ {result.service_name}: {result.status} ({result.response_time:.3f}s)")
            else:
                logger.error(f"✗ {result.service_name}: {result.status} - {result.error_message}")
    
    def _format_results(self) -> Dict[str, Any]:
        """Formatear resultados para API"""
        return {
            'timestamp': self.last_check_time.isoformat(),
            'overall_status': self.overall_status,
            'total_checks': len(self.check_results),
            'healthy_checks': sum(1 for r in self.check_results if r.status == 'healthy'),
            'degraded_checks': sum(1 for r in self.check_results if r.status == 'degraded'),
            'unhealthy_checks': sum(1 for r in self.check_results if r.status == 'unhealthy'),
            'checks': [
                {
                    'service': result.service_name,
                    'status': result.status,
                    'response_time': result.response_time,
                    'error_message': result.error_message,
                    'metadata': result.metadata
                }
                for result in self.check_results
            ]
        }
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Obtener resumen de estado"""
        if not self.check_results:
            return {'status': 'no_checks_run', 'message': 'No se han ejecutado health checks'}
        
        return {
            'overall_status': self.overall_status,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'total_services': len(self.check_results),
            'healthy_services': sum(1 for r in self.check_results if r.status == 'healthy')
        }

# Instancia global del health checker
health_checker = WhatsAppHealthChecker()

def run_health_check() -> Dict[str, Any]:
    """Función de conveniencia para ejecutar health check"""
    return health_checker.run_all_checks()

def get_health_status() -> Dict[str, Any]:
    """Función de conveniencia para obtener estado"""
    return health_checker.get_status_summary()