# -*- coding: utf-8 -*-
"""
Cloud Logging Manager - Adaptado para Frappe Cloud
===================================================

Sistema de logging optimizado para entornos cloud-native que combina:
- Logging nativo de Frappe (console/archivo)
- Webhook emitter para servicios externos (Elastic Cloud, Datadog)
- Buffer inteligente y retry automático
- Compresión y rate limiting

Autor: KREO Colombia
Versión: 2.0.0
Fecha: 2025-01-27
"""

import frappe
import json
import gzip
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
from threading import Lock
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class CloudLogContext:
    """Contexto completo de un evento de log para entornos cloud"""
    timestamp: str
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    service: str  # kreo-whatsapp
    environment: str  # production, staging, development
    operation: str  # send_message, receive_webhook, etc
    message: str
    
    # Identificadores
    correlation_id: Optional[str] = None
    user: Optional[str] = None
    session_id: Optional[str] = None
    
    # WhatsApp específico
    message_id: Optional[str] = None
    recipient: Optional[str] = None
    template_name: Optional[str] = None
    status: Optional[str] = None
    
    # Performance
    response_time_ms: Optional[float] = None
    queue_time_ms: Optional[float] = None
    
    # Metadata adicional
    metadata: Optional[Dict[str, Any]] = None
    
    # Cloud info
    cloud_provider: str = "frappe_cloud"
    site_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para serialización"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convertir a JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class WebhookLogEmitter:
    """
    Emisor de logs vía webhook HTTP a servicios externos
    Características:
    - Envío batch para optimizar bandwidth
    - Compresión GZIP
    - Retry automático con exponential backoff
    - Rate limiting
    - Queue local para resiliencia
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.webhook_url = config.get('webhook_url')
        self.api_key = config.get('api_key')
        self.batch_size = config.get('batch_size', 50)
        self.batch_timeout = config.get('batch_timeout_seconds', 10)
        self.compression = config.get('compression', 'gzip')
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_backoff = config.get('retry_backoff', 2)
        
        # Buffer local
        self.buffer: deque = deque(maxlen=1000)
        self.buffer_lock = Lock()
        self.last_flush_time = time.time()
        
        # HTTP session con retry
        self.session = self._create_session()
        
        # Estadísticas
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'total_compressed_bytes': 0,
            'last_send_time': None
        }
    
    def _create_session(self) -> requests.Session:
        """Crear sesión HTTP con retry automático"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=self.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Headers comunes
        session.headers.update({
            'Content-Type': 'application/x-ndjson',
            'Authorization': f'ApiKey {self.api_key}',
            'User-Agent': 'KREO-WhatsApp-CloudLogger/2.0'
        })
        
        if self.compression == 'gzip':
            session.headers['Content-Encoding'] = 'gzip'
        
        return session
    
    def add_to_buffer(self, log_context: CloudLogContext):
        """Agregar log al buffer local"""
        if not self.enabled or not self.webhook_url:
            return
        
        with self.buffer_lock:
            self.buffer.append(log_context)
        
        # Auto-flush si se alcanza tamaño de batch o timeout
        if (len(self.buffer) >= self.batch_size or 
            time.time() - self.last_flush_time >= self.batch_timeout):
            self.flush()
    
    def flush(self) -> bool:
        """Enviar logs acumulados al webhook"""
        if not self.enabled or not self.webhook_url:
            return False
        
        with self.buffer_lock:
            if not self.buffer:
                return True
            
            # Tomar batch actual
            batch = list(self.buffer)
            self.buffer.clear()
            self.last_flush_time = time.time()
        
        try:
            # Preparar payload en formato NDJSON (Newline Delimited JSON)
            # Compatible con Elasticsearch Bulk API
            ndjson_lines = []
            for log in batch:
                # Index action (para Elasticsearch)
                index_action = {
                    "index": {
                        "_index": f"kreo-whatsapp-logs-{datetime.utcnow().strftime('%Y.%m.%d')}"
                    }
                }
                ndjson_lines.append(json.dumps(index_action))
                ndjson_lines.append(log.to_json())
            
            payload = '\n'.join(ndjson_lines) + '\n'
            payload_bytes = payload.encode('utf-8')
            
            # Comprimir si está habilitado
            if self.compression == 'gzip':
                payload_bytes = gzip.compress(payload_bytes, compresslevel=6)
            
            # Enviar
            response = self.session.post(
                self.webhook_url,
                data=payload_bytes,
                timeout=30
            )
            
            response.raise_for_status()
            
            # Actualizar estadísticas
            self.stats['total_sent'] += len(batch)
            self.stats['total_compressed_bytes'] += len(payload_bytes)
            self.stats['last_send_time'] = datetime.utcnow().isoformat()
            
            frappe.logger().debug(
                f"✓ Webhook emitter: {len(batch)} logs sent successfully "
                f"({len(payload_bytes)} bytes)"
            )
            
            return True
            
        except Exception as e:
            self.stats['total_failed'] += len(batch)
            frappe.logger().error(f"✗ Webhook emitter failed: {str(e)}")
            
            # Re-agregar al buffer para retry (con límite)
            with self.buffer_lock:
                for log in batch[:100]:  # Solo primeros 100 para evitar overflow
                    self.buffer.appendleft(log)
            
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del emitter"""
        return {
            **self.stats,
            'buffer_size': len(self.buffer),
            'buffer_max_size': self.buffer.maxlen
        }


class CloudLoggingManager:
    """
    Gestor de logging optimizado para Frappe Cloud
    
    Características:
    - Dual output: Frappe nativo + Webhook externo
    - Buffer inteligente con auto-flush
    - Correlación de operaciones
    - Métricas de performance
    - Compatibilidad con sistema actual
    """
    
    def __init__(self):
        self.config = self._load_config()
        self.environment = self.config.get('environment', 'production')
        self.site_name = frappe.local.site if hasattr(frappe, 'local') else None
        
        # Configuración de dual output
        self.dual_output = self.config.get('cloud_logging', {}).get('dual_output', True)
        self.frappe_native = self.config.get('cloud_logging', {}).get('frappe_native', True)
        self.external_enabled = self.config.get('cloud_logging', {}).get('external_enabled', True)
        
        # Webhook emitter
        self.webhook_emitter = None
        if self.external_enabled:
            elastic_config = self.config.get('elastic_cloud', {})
            if elastic_config.get('url'):
                webhook_config = {
                    'enabled': True,
                    'webhook_url': elastic_config['url'],
                    'api_key': elastic_config.get('api_key'),
                    'batch_size': elastic_config.get('batch_size', 50),
                    'batch_timeout_seconds': elastic_config.get('batch_timeout_seconds', 10),
                    'compression': elastic_config.get('compression', 'gzip'),
                    'retry_attempts': elastic_config.get('retry_attempts', 3),
                    'retry_backoff': elastic_config.get('retry_backoff', 2)
                }
                self.webhook_emitter = WebhookLogEmitter(webhook_config)
        
        # Cache de correlación
        self._correlation_cache = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """Cargar configuración desde site_config"""
        return {
            'environment': frappe.conf.get('environment', 'production'),
            'cloud_logging': frappe.conf.get('cloud_logging', {}),
            'elastic_cloud': frappe.conf.get('elastic_cloud', {}),
            'datadog': frappe.conf.get('datadog', {})
        }
    
    def log_event(
        self,
        operation: str,
        level: str,
        message: str,
        correlation_id: Optional[str] = None,
        user: Optional[str] = None,
        message_id: Optional[str] = None,
        recipient: Optional[str] = None,
        template_name: Optional[str] = None,
        status: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Registrar evento de log con dual output
        
        Args:
            operation: Nombre de la operación (e.g., "send_message")
            level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Mensaje descriptivo
            correlation_id: ID para correlacionar operaciones relacionadas
            user: Usuario que ejecuta la operación
            message_id: ID del mensaje de WhatsApp
            recipient: Número del destinatario
            template_name: Nombre de template usado
            status: Estado de la operación
            response_time_ms: Tiempo de respuesta en ms
            metadata: Metadata adicional
        """
        try:
            # Crear contexto de log
            log_context = CloudLogContext(
                timestamp=datetime.utcnow().isoformat() + 'Z',
                level=level,
                service='kreo-whatsapp',
                environment=self.environment,
                operation=operation,
                message=message,
                correlation_id=correlation_id or self._generate_correlation_id(),
                user=user or frappe.session.user if hasattr(frappe, 'session') else None,
                session_id=frappe.session.sid if hasattr(frappe, 'session') else None,
                message_id=message_id,
                recipient=recipient,
                template_name=template_name,
                status=status,
                response_time_ms=response_time_ms,
                metadata=metadata,
                cloud_provider='frappe_cloud',
                site_name=self.site_name
            )
            
            # Output 1: Frappe native logging
            if self.frappe_native:
                self._log_to_frappe(log_context)
            
            # Output 2: External webhook
            if self.external_enabled and self.webhook_emitter:
                self.webhook_emitter.add_to_buffer(log_context)
            
        except Exception as e:
            # Fallback: al menos loggear el error
            frappe.logger().error(f"CloudLoggingManager error: {str(e)}")
    
    def _log_to_frappe(self, log_context: CloudLogContext):
        """Log usando sistema nativo de Frappe"""
        # Construir mensaje formateado
        formatted_msg = (
            f"[{log_context.operation}] {log_context.message}"
        )
        
        if log_context.message_id:
            formatted_msg += f" | msg_id={log_context.message_id}"
        
        if log_context.recipient:
            formatted_msg += f" | recipient={log_context.recipient}"
        
        if log_context.response_time_ms:
            formatted_msg += f" | response_time={log_context.response_time_ms}ms"
        
        # Log según nivel
        logger = frappe.logger()
        if log_context.level == 'DEBUG':
            logger.debug(formatted_msg)
        elif log_context.level == 'INFO':
            logger.info(formatted_msg)
        elif log_context.level == 'WARNING':
            logger.warning(formatted_msg)
        elif log_context.level == 'ERROR':
            logger.error(formatted_msg)
        elif log_context.level == 'CRITICAL':
            logger.critical(formatted_msg)
    
    def _generate_correlation_id(self) -> str:
        """Generar ID de correlación único"""
        import uuid
        return f"corr-{uuid.uuid4().hex[:16]}"
    
    def start_operation(self, operation: str, metadata: Optional[Dict] = None) -> str:
        """
        Iniciar una operación trackeada
        
        Returns:
            correlation_id para usar en logs subsiguientes
        """
        correlation_id = self._generate_correlation_id()
        
        self._correlation_cache[correlation_id] = {
            'operation': operation,
            'start_time': time.time(),
            'metadata': metadata or {}
        }
        
        self.log_event(
            operation=operation,
            level='INFO',
            message=f"Operation started: {operation}",
            correlation_id=correlation_id,
            metadata=metadata
        )
        
        return correlation_id
    
    def end_operation(
        self,
        correlation_id: str,
        success: bool = True,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Finalizar una operación trackeada"""
        if correlation_id not in self._correlation_cache:
            return
        
        op_data = self._correlation_cache.pop(correlation_id)
        response_time_ms = (time.time() - op_data['start_time']) * 1000
        
        final_metadata = {**op_data['metadata'], **(metadata or {})}
        
        self.log_event(
            operation=op_data['operation'],
            level='INFO' if success else 'ERROR',
            message=message or f"Operation {'completed' if success else 'failed'}: {op_data['operation']}",
            correlation_id=correlation_id,
            status='success' if success else 'failed',
            response_time_ms=response_time_ms,
            metadata=final_metadata
        )
    
    def flush_buffers(self):
        """Forzar envío de logs pendientes"""
        if self.webhook_emitter:
            self.webhook_emitter.flush()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del logging manager"""
        stats = {
            'dual_output_enabled': self.dual_output,
            'frappe_native_enabled': self.frappe_native,
            'external_enabled': self.external_enabled,
            'active_operations': len(self._correlation_cache)
        }
        
        if self.webhook_emitter:
            stats['webhook_emitter'] = self.webhook_emitter.get_stats()
        
        return stats


# Singleton global
_cloud_logging_manager = None


def get_cloud_logging_manager() -> CloudLoggingManager:
    """Obtener instancia singleton del CloudLoggingManager"""
    global _cloud_logging_manager
    
    if _cloud_logging_manager is None:
        _cloud_logging_manager = CloudLoggingManager()
    
    return _cloud_logging_manager


# Alias para compatibilidad con código existente
cloud_logging_manager = get_cloud_logging_manager()


# API simplificada para uso común
def log_whatsapp_event(
    operation: str,
    level: str,
    message: str,
    **kwargs
):
    """
    Función de conveniencia para logging de eventos WhatsApp
    
    Example:
        log_whatsapp_event(
            "send_message",
            "INFO",
            "Message sent successfully",
            message_id="wamid.123",
            recipient="+573001234567",
            response_time_ms=245.5
        )
    """
    manager = get_cloud_logging_manager()
    manager.log_event(operation, level, message, **kwargs)


def log_error(operation: str, error: Exception, **kwargs):
    """
    Función de conveniencia para logging de errores
    
    Example:
        try:
            send_message(...)
        except Exception as e:
            log_error("send_message", e, message_id="wamid.123")
    """
    manager = get_cloud_logging_manager()
    manager.log_event(
        operation=operation,
        level='ERROR',
        message=f"Error: {str(error)}",
        metadata={
            'error_type': type(error).__name__,
            'error_details': str(error),
            **kwargs.get('metadata', {})
        },
        **{k: v for k, v in kwargs.items() if k != 'metadata'}
    )


# Decorador para tracking automático de operaciones
def track_operation(operation_name: str):
    """
    Decorador para trackear automáticamente una operación
    
    Example:
        @track_operation("send_template_message")
        def send_template(recipient, template_name):
            # ... código ...
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_cloud_logging_manager()
            correlation_id = manager.start_operation(operation_name)
            
            try:
                result = func(*args, **kwargs)
                manager.end_operation(correlation_id, success=True)
                return result
            except Exception as e:
                manager.end_operation(
                    correlation_id,
                    success=False,
                    message=f"Error: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator