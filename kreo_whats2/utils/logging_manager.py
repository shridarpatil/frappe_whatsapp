# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from functools import wraps
import traceback
import socket
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import time

# Importar dependencias para ELK Stack
try:
    import elasticsearch
    from elasticsearch import Elasticsearch
    ELK_AVAILABLE = True
except ImportError:
    ELK_AVAILABLE = False
    print("Advertencia: Elasticsearch no disponible. Instale 'elasticsearch' para integración completa.")

# Importar nuevos componentes de logging
try:
    from kreo_whats2.kreo_whats2.utils.log_analytics import analytics_engine, add_log_for_analysis
    from kreo_whats2.kreo_whats2.utils.alert_manager import alert_manager, trigger_manual_alert
    ANALYTICS_AVAILABLE = True
    ALERT_MANAGER_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    ALERT_MANAGER_AVAILABLE = False
    print("Advertencia: Componentes avanzados de logging no disponibles.")

@dataclass
class LogContext:
    """Contexto de logging estructurado"""
    timestamp: str
    level: str
    service: str
    operation: str
    user: str = "system"
    session: str = "unknown"
    message_id: str = None
    template: str = None
    recipient: str = None
    status: str = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    business_metrics: Dict[str, Any] = field(default_factory=dict)
    security_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    hostname: str = field(default_factory=socket.gethostname)
    process_id: int = field(default_factory=os.getpid)
    thread_id: int = field(default_factory=threading.get_ident)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

class WhatsAppLoggingManager:
    """Gestor centralizado de logging para WhatsApp Business API con integración ELK Stack"""
    
    def __init__(self):
        self.loggers = {}
        self.log_level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        self.elk_client = None
        self.log_context_stack = []
        self.performance_trackers = {}
        self._setup_base_logger()
        self._setup_elk_integration()
        self._start_log_processor()
    
    def _setup_base_logger(self):
        """Configurar logger base con soporte para logging estructurado"""
        # Crear logger base
        self.base_logger = logging.getLogger("kreo_whats2")
        self.base_logger.setLevel(logging.INFO)
        
        # Evitar duplicados
        if not self.base_logger.handlers:
            # Handler para consola con formato JSON
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(StructuredFormatter())
            
            # Handler para archivo con rotación avanzada
            log_dir = "logs/whatsapp"
            os.makedirs(log_dir, exist_ok=True)
            
            # Log principal con rotación diaria
            file_handler = logging.handlers.TimedRotatingFileHandler(
                f"{log_dir}/whatsapp.log",
                when='midnight',
                interval=1,
                backupCount=30,  # 30 días de retención
                encoding='utf-8'
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(StructuredFormatter())
            
            # Log de errores separado
            error_handler = logging.handlers.TimedRotatingFileHandler(
                f"{log_dir}/whatsapp_errors.log",
                when='midnight',
                interval=1,
                backupCount=90,  # 90 días de retención para errores
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(StructuredFormatter())
            
            # Agregar handlers
            self.base_logger.addHandler(console_handler)
            self.base_logger.addHandler(file_handler)
            self.base_logger.addHandler(error_handler)
    
    def _setup_elk_integration(self):
        """Configurar integración con ELK Stack"""
        if not ELK_AVAILABLE:
            self.base_logger.warning("Elasticsearch no disponible. La integración con ELK Stack está deshabilitada.")
            return
        
        try:
            # Configurar cliente Elasticsearch desde variables de entorno
            elk_host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
            elk_port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
            elk_index = os.getenv('ELASTICSEARCH_INDEX', 'kreo-whatsapp-logs')
            
            self.elk_client = Elasticsearch(
                [{'host': elk_host, 'port': elk_port, 'scheme': 'http'}],
                timeout=30,
                max_retries=5,
                retry_on_timeout=True
            )
            
            # Verificar conexión
            if self.elk_client.ping():
                self.base_logger.info(f"Conexión exitosa a Elasticsearch en {elk_host}:{elk_port}")
                self._create_index_template(elk_index)
            else:
                self.base_logger.error("No se pudo conectar a Elasticsearch")
                
        except Exception as e:
            self.base_logger.error(f"Error configurando ELK integration: {str(e)}")
    
    def _create_index_template(self, index_name: str):
        """Crear template de índice para logs de WhatsApp"""
        try:
            template_body = {
                "index_patterns": [f"{index_name}-*"],
                "template": {
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "level": {"type": "keyword"},
                            "service": {"type": "keyword"},
                            "operation": {"type": "keyword"},
                            "user": {"type": "keyword"},
                            "session": {"type": "keyword"},
                            "message_id": {"type": "keyword"},
                            "template": {"type": "keyword"},
                            "recipient": {"type": "keyword"},
                            "status": {"type": "keyword"},
                            "error_details": {
                                "properties": {
                                    "error_type": {"type": "keyword"},
                                    "error_message": {"type": "text"},
                                    "stack_trace": {"type": "text"},
                                    "retry_count": {"type": "integer"},
                                    "fallback_used": {"type": "boolean"}
                                }
                            },
                            "performance_metrics": {
                                "properties": {
                                    "response_time_ms": {"type": "float"},
                                    "queue_time_ms": {"type": "float"},
                                    "processing_time_ms": {"type": "float"},
                                    "total_time_ms": {"type": "float"}
                                }
                            },
                            "business_metrics": {
                                "properties": {
                                    "messages_sent": {"type": "integer"},
                                    "messages_failed": {"type": "integer"},
                                    "messages_delivered": {"type": "integer"},
                                    "messages_read": {"type": "integer"}
                                }
                            },
                            "security_context": {
                                "properties": {
                                    "ip_address": {"type": "ip"},
                                    "user_agent": {"type": "text"},
                                    "authentication_method": {"type": "keyword"},
                                    "sensitive_operation": {"type": "boolean"}
                                }
                            },
                            "hostname": {"type": "keyword"},
                            "process_id": {"type": "integer"},
                            "thread_id": {"type": "keyword"},
                            "correlation_id": {"type": "keyword"},
                            "metadata": {"type": "object", "dynamic": True}
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                        "index.lifecycle.name": "whatsapp-logs-policy",
                        "index.lifecycle.rollover_alias": f"{index_name}"
                    }
                }
            }
            
            if not self.elk_client.indices.exists_index_template("whatsapp-logs-template"):
                self.elk_client.indices.put_index_template(
                    name="whatsapp-logs-template",
                    body=template_body
                )
                self.base_logger.info("Template de índice creado para logs de WhatsApp")
                
        except Exception as e:
            self.base_logger.error(f"Error creando template de índice: {str(e)}")
    
    def _start_log_processor(self):
        """Iniciar procesador de logs en segundo plano"""
        def process_logs():
            while True:
                try:
                    self._process_pending_logs()
                    time.sleep(5)  # Procesar cada 5 segundos
                except Exception as e:
                    self.base_logger.error(f"Error en procesador de logs: {str(e)}")
                    time.sleep(10)
        
        thread = threading.Thread(target=process_logs, daemon=True)
        thread.start()
        self.base_logger.info("Procesador de logs iniciado")
    
    def _process_pending_logs(self):
        """Procesar logs pendientes para envío a ELK"""
        # Implementación para procesamiento batch de logs
        pass
    
    def get_logger(self, name: str) -> logging.Logger:
        """Obtener logger para un módulo específico"""
        if name not in self.loggers:
            logger = logging.getLogger(f"kreo_whats2.{name}")
            logger.setLevel(logging.INFO)
            
            # Configurar handlers desde el logger base
            for handler in self.base_logger.handlers:
                logger.addHandler(handler)
            
            self.loggers[name] = logger
        
        return self.loggers[name]

class StructuredFormatter(logging.Formatter):
    """Formateador para logs estructurados en JSON"""
    
    def format(self, record):
        # Crear payload JSON estructurado
        log_data = {
            "@timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "service": "kreo_whats2",
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "thread": record.thread,
            "process": record.process,
            "hostname": socket.gethostname()
        }
        
        # Agregar excepciones si existen
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Agregar datos extra si existen
        if hasattr(record, 'structured_data'):
            log_data.update(record.structured_data)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)

    def formatException(self, exc_info):
        """Formatear excepciones para JSON"""
        import traceback
        return {
            "type": exc_info[0].__name__,
            "message": str(exc_info[1]),
            "traceback": traceback.format_exception(*exc_info)
        }

    def formatStack(self, stack_info):
        """Formatear stack trace para JSON"""
        import traceback
        return traceback.format_stack(stack_info)
    
    def setup_module_logging(self, module_name: str, whatsapp_settings=None):
        """Configurar logging para un módulo específico"""
        try:
            if not whatsapp_settings:
                whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enable_detailed_logging:
                return
            
            logger = self.get_logger(module_name)
            log_level = self.log_level_mapping.get(
                whatsapp_settings.log_level.upper(), 
                logging.INFO
            )
            logger.setLevel(log_level)
            
            # Configurar handler específico para el módulo
            log_dir = whatsapp_settings.log_file_path or "logs/whatsapp"
            os.makedirs(log_dir, exist_ok=True)
            
            module_file_handler = logging.handlers.RotatingFileHandler(
                f"{log_dir}/{module_name}.log",
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            )
            module_file_handler.setLevel(log_level)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            module_file_handler.setFormatter(formatter)
            
            # Agregar handler si no existe
            existing_handlers = [h for h in logger.handlers 
                              if isinstance(h, logging.FileHandler) and 
                              h.baseFilename.endswith(f"{module_name}.log")]
            
            if not existing_handlers:
                logger.addHandler(module_file_handler)
            
            logger.info(f"Logging configurado para módulo {module_name} en nivel {log_level}")
            
        except Exception as e:
            self.base_logger.error(f"Error configurando logging para {module_name}: {str(e)}")
    
    def log_event(self, module: str, level: str, message: str, **kwargs):
        """Registrar evento de logging estructurado con contexto completo"""
        try:
            logger = self.get_logger(module)
            log_level = self.log_level_mapping.get(level.upper(), logging.INFO)
            
            # Crear contexto de logging
            context = LogContext(
                timestamp=datetime.now().isoformat(),
                level=level.upper(),
                service="kreo_whats2",
                operation=kwargs.get("operation", "unknown"),
                user=kwargs.get("user", frappe.session.user if frappe.session else "system"),
                session=kwargs.get("session", "unknown"),
                message_id=kwargs.get("message_id"),
                template=kwargs.get("template"),
                recipient=kwargs.get("recipient"),
                status=kwargs.get("status"),
                error_details=kwargs.get("error_details", {}),
                performance_metrics=kwargs.get("performance_metrics", {}),
                business_metrics=kwargs.get("business_metrics", {}),
                security_context=kwargs.get("security_context", {}),
                metadata=kwargs.get("metadata", {})
            )
            
            # Agregar datos estructurados al record
            record = logger.makeRecord(
                name=logger.name,
                level=log_level,
                fn="",
                lno=0,
                msg=message,
                args=(),
                exc_info=None
            )
            record.structured_data = context.__dict__
            
            # Enviar al logger
            logger.handle(record)
            
            # Enviar a Elasticsearch si está disponible
            if self.elk_client:
                self._send_to_elk(context.__dict__)
            
            # Enviar a Log Analytics si está disponible
            if ANALYTICS_AVAILABLE:
                try:
                    add_log_for_analysis(context.__dict__)
                except Exception as e:
                    self.base_logger.warning(f"Error enviando a Log Analytics: {str(e)}")
                
        except Exception as e:
            self.base_logger.error(f"Error registrando evento: {str(e)}")
    
    def log_whatsapp_message(self, message_data: Dict[str, Any], status: str, **kwargs):
        """Registrar evento específico de mensaje de WhatsApp"""
        try:
            context = {
                "operation": "whatsapp_message",
                "message_id": message_data.get("message_id"),
                "template": message_data.get("template_name"),
                "recipient": message_data.get("to"),
                "status": status,
                "business_metrics": {
                    "messages_sent": 1 if status == "sent" else 0,
                    "messages_failed": 1 if status == "failed" else 0,
                    "messages_delivered": 1 if status == "delivered" else 0,
                    "messages_read": 1 if status == "read" else 0
                },
                "performance_metrics": kwargs.get("performance_metrics", {}),
                "error_details": kwargs.get("error_details", {}),
                "metadata": {
                    "message_type": message_data.get("type"),
                    "channel": "whatsapp",
                    "integration": "meta"
                }
            }
            
            self.log_event("whatsapp_message", "INFO", f"Mensaje WhatsApp: {status}", **context)
            
        except Exception as e:
            self.base_logger.error(f"Error registrando mensaje WhatsApp: {str(e)}")
    
    def log_performance_metric(self, operation: str, duration_ms: float, **kwargs):
        """Registrar métrica de performance con contexto"""
        try:
            performance_data = {
                "operation": operation,
                "duration_ms": duration_ms,
                "status": kwargs.get("status", "success"),
                "performance_metrics": {
                    "response_time_ms": kwargs.get("response_time_ms", duration_ms),
                    "queue_time_ms": kwargs.get("queue_time_ms", 0),
                    "processing_time_ms": kwargs.get("processing_time_ms", duration_ms),
                    "total_time_ms": duration_ms
                },
                "business_metrics": kwargs.get("business_metrics", {}),
                "metadata": kwargs.get("metadata", {})
            }
            
            self.log_event("performance", "INFO", f"Performance: {operation} - {duration_ms}ms", **performance_data)
            
        except Exception as e:
            self.base_logger.error(f"Error registrando métrica de performance: {str(e)}")
    
    def log_security_event(self, event_type: str, **kwargs):
        """Registrar evento de seguridad"""
        try:
            security_data = {
                "operation": "security_audit",
                "security_context": {
                    "event_type": event_type,
                    "ip_address": kwargs.get("ip_address"),
                    "user_agent": kwargs.get("user_agent"),
                    "authentication_method": kwargs.get("auth_method"),
                    "sensitive_operation": kwargs.get("sensitive_operation", False),
                    "user": kwargs.get("user", "system")
                },
                "status": kwargs.get("status", "info"),
                "metadata": kwargs.get("metadata", {})
            }
            
            level = "CRITICAL" if kwargs.get("critical", False) else "WARNING"
            self.log_event("security", level, f"Evento de seguridad: {event_type}", **security_data)
            
            # Enviar alerta automática si es un evento crítico
            if ALERT_MANAGER_AVAILABLE and kwargs.get("critical", False):
                try:
                    trigger_manual_alert("whatsapp_security_anomaly", f"Evento de seguridad crítico: {event_type}")
                except Exception as e:
                    self.base_logger.warning(f"Error enviando alerta de seguridad: {str(e)}")
            
        except Exception as e:
            self.base_logger.error(f"Error registrando evento de seguridad: {str(e)}")
    
    def start_operation_context(self, operation_name: str, **kwargs) -> str:
        """Iniciar contexto de operación para seguimiento"""
        correlation_id = str(uuid.uuid4())
        context = {
            "operation": operation_name,
            "correlation_id": correlation_id,
            "start_time": datetime.now().isoformat(),
            "user": kwargs.get("user", "system"),
            "metadata": kwargs.get("metadata", {})
        }
        
        self.log_context_stack.append(context)
        self.performance_trackers[correlation_id] = {
            "operation": operation_name,
            "start_time": time.time(),
            "steps": []
        }
        
        self.log_event("operation", "INFO", f"Iniciando operación: {operation_name}", **context)
        return correlation_id
    
    def end_operation_context(self, correlation_id: str, status: str = "success", **kwargs):
        """Finalizar contexto de operación"""
        if correlation_id in self.performance_trackers:
            tracker = self.performance_trackers[correlation_id]
            duration = time.time() - tracker["start_time"]
            
            context = {
                "operation": tracker["operation"],
                "correlation_id": correlation_id,
                "status": status,
                "performance_metrics": {
                    "total_time_ms": duration * 1000,
                    "steps": tracker["steps"]
                },
                "business_metrics": kwargs.get("business_metrics", {}),
                "error_details": kwargs.get("error_details", {}) if status == "error" else {},
                "metadata": kwargs.get("metadata", {})
            }
            
            level = "ERROR" if status == "error" else "INFO"
            self.log_event("operation", level, f"Operación finalizada: {tracker['operation']} - {status}", **context)
            
            # Limpiar seguimiento
            del self.performance_trackers[correlation_id]
    
    def add_operation_step(self, correlation_id: str, step_name: str, duration_ms: float = None):
        """Agregar paso a operación en seguimiento"""
        if correlation_id in self.performance_trackers:
            step = {
                "step": step_name,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat()
            }
            self.performance_trackers[correlation_id]["steps"].append(step)
    
    def _send_to_elk(self, log_data: Dict[str, Any]):
        """Enviar log a Elasticsearch de forma asíncrona"""
        try:
            if not self.elk_client:
                return
            
            # Usar threading para envío asíncrono
            def send_async():
                try:
                    index_name = f"kreo-whatsapp-logs-{datetime.now().strftime('%Y.%m.%d')}"
                    self.elk_client.index(
                        index=index_name,
                        document=log_data
                    )
                except Exception as e:
                    self.base_logger.warning(f"Error enviando a ELK: {str(e)}")
            
            thread = threading.Thread(target=send_async, daemon=True)
            thread.start()
            
        except Exception as e:
            self.base_logger.error(f"Error en envío a ELK: {str(e)}")
    
    def log_error(self, module: str, error: Exception, context: dict = None):
        """Registrar error con stack trace"""
        try:
            logger = self.get_logger(module)
            
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "module": module,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "context": context or {},
                "user": frappe.session.user if frappe.session else "system"
            }
            
            logger.error(json.dumps(error_data, ensure_ascii=False))
            
            # Registrar en base de datos si está disponible
            self._log_error_to_database(error_data)
            
        except Exception as e:
            self.base_logger.error(f"Error registrando error: {str(e)}")
    
    def _log_error_to_database(self, error_data: dict):
        """Registrar error en base de datos de Frappe"""
        try:
            # Verificar si estamos en un contexto de Frappe
            if not frappe.db:
                return
            
            # Crear documento de log de error
            error_log = frappe.get_doc({
                "doctype": "Error Log",
                "method": "kreo_whats2.error",
                "error": json.dumps(error_data, ensure_ascii=False),
                "page": frappe.request.path if frappe.request else "unknown"
            })
            error_log.insert(ignore_permissions=True)
            
        except Exception as e:
            self.base_logger.error(f"Error registrando en base de datos: {str(e)}")
    
    def log_performance(self, module: str, operation: str, duration: float, **kwargs):
        """Registrar métricas de performance"""
        try:
            logger = self.get_logger(module)
            
            perf_data = {
                "timestamp": datetime.now().isoformat(),
                "module": module,
                "operation": operation,
                "duration_ms": duration * 1000,
                "status": kwargs.get("status", "success"),
                "metadata": kwargs.get("metadata", {})
            }
            
            logger.info(f"PERF: {json.dumps(perf_data)}")
            
        except Exception as e:
            self.base_logger.error(f"Error registrando performance: {str(e)}")

def log_whatsapp_event(level: str = "INFO", module: str = "general"):
    """Decorador para logging automático de eventos WhatsApp"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger_manager = WhatsAppLoggingManager()
            logger = logger_manager.get_logger(module)
            
            start_time = datetime.now()
            
            try:
                logger.log(
                    logger_manager.log_level_mapping.get(level.upper(), logging.INFO),
                    f"Iniciando {func.__name__}"
                )
                
                result = func(*args, **kwargs)
                
                duration = (datetime.now() - start_time).total_seconds()
                logger_manager.log_performance(
                    module, func.__name__, duration, status="success"
                )
                
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger_manager.log_performance(
                    module, func.__name__, duration, status="error"
                )
                logger_manager.log_error(module, e, {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                })
                raise
                
        return wrapper
    return decorator

def handle_whatsapp_errors(module: str = "general"):
    """Decorador para manejo centralizado de errores WhatsApp"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger_manager = WhatsAppLoggingManager()
            
            try:
                return func(*args, **kwargs)
                
            except frappe.exceptions.ValidationError as e:
                # Errores de validación de Frappe
                logger_manager.log_event(
                    module, "WARNING", f"Error de validación: {str(e)}",
                    metadata={"error_type": "validation", "function": func.__name__}
                )
                raise
                
            except requests.exceptions.RequestException as e:
                # Errores de red/HTTP
                logger_manager.log_event(
                    module, "ERROR", f"Error de red: {str(e)}",
                    metadata={"error_type": "network", "function": func.__name__}
                )
                return {"success": False, "error": "Error de conexión", "retryable": True}
                
            except Exception as e:
                # Errores generales
                logger_manager.log_error(module, e, {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                })
                return {"success": False, "error": "Error interno del servidor"}
                
        return wrapper
    return decorator

# Instancia global del gestor de logging
logging_manager = WhatsAppLoggingManager()

# Funciones de conveniencia
def get_logger(module: str) -> logging.Logger:
    """Obtener logger para un módulo"""
    return logging_manager.get_logger(module)

def log_event(module: str, level: str, message: str, **kwargs):
    """Registrar evento"""
    return logging_manager.log_event(module, level, message, **kwargs)

def log_error(module: str, error: Exception, context: dict = None):
    """Registrar error"""
    return logging_manager.log_error(module, error, context)

def log_performance(module: str, operation: str, duration: float, **kwargs):
    """Registrar performance"""
    return logging_manager.log_performance(module, operation, duration, **kwargs)