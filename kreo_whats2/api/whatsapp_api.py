# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
import requests
import redis
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
import threading

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event,
        handle_whatsapp_errors, get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
    logger = get_logger("whatsapp_api")
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible")

class CircuitBreaker:
    """Implementación de Circuit Breaker para WhatsApp API"""
    
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.next_attempt = None
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self.next_attempt and time.time() > self.next_attempt:
                    # Intentar la llamada
                    result = func(*args, **kwargs)
                    if result.get("success", False):
                        self._on_failure()
                    else:
                        self._on_success()
                    return result
                else:
                    # Rechazar llamada
                    return {"success": False, "error": "Circuit breaker is OPEN"}
            
            elif self.state == "HALF_OPEN":
                # Permitir algunas llamadas para probar
                result = func(*args, **kwargs)
                if result.get("success", False):
                    self._on_failure()
                else:
                    self._on_success()
                return result
            
            else:  # CLOSED
                # Verificar si podemos abrir el circuito
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                    self.next_attempt = time.time() + 30  # Esperar 30 segundos antes de intentar
                    return func(*args, **kwargs)
                else:
                    return {"success": False, "error": "Circuit breaker is CLOSED"}
        
        return wrapper
    
    def _on_success(self):
        """Manejar éxito"""
        self.failure_count = 0
        self.state = "CLOSED"
        self.next_attempt = None
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_event("circuit_breaker", "success", {
                "state": self.state,
                "failure_count": self.failure_count
            })
        else:
            logger.info("Circuit breaker CLOSED after successful call")
    
    def _on_failure(self):
        """Manejar fallo"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.next_attempt = time.time() + self.timeout
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("circuit_breaker", "failure_threshold_reached", {
                    "state": self.state,
                    "failure_count": self.failure_count,
                    "threshold": self.failure_threshold
                })
            else:
                logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    def _should_attempt_reset(self):
        """Verificar si debemos intentar resetear el circuito"""
        if self.state == "OPEN":
            return time.time() > self.next_attempt
        
        if self.state == "CLOSED" and self.last_failure_time:
            # Resetear después de 5 minutos sin fallos
            if time.time() - self.last_failure_time > 300:
                return True
        
        return False

class RateLimiter:
    """Implementación de Rate Limiting para WhatsApp API"""
    
    def __init__(self, redis_url="redis://redis-queue:6379/1", limit_per_second=10, window_size=60):
        self.redis_url = redis_url
        self.limit_per_second = limit_per_second
        self.window_size = window_size
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Conectar a Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("rate_limiter", "redis_connected", {
                    "redis_url": self.redis_url
                })
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("rate_limiter", e, {
                    "operation": "_connect_redis",
                    "redis_url": self.redis_url
                })
            else:
                logger.error(f"Error conectando a Redis: {str(e)}")
            self.redis_client = None
    
    def is_allowed(self, identifier="default"):
        """Verificar si se permite enviar mensaje"""
        if not self.redis_client:
            return False
        
        try:
            current_time = datetime.now()
            key = f"whatsapp_rate_limit:{identifier}:{current_time.strftime('%Y-%m-%d %H:%M')}"
            
            # Obtener uso actual
            current_usage = self.redis_client.get(key) or 0
            current_usage = int(current_usage)
            
            # Verificar límite
            if current_usage < self.limit_per_second:
                # Incrementar contador
                self.redis_client.incr(key)
                self.redis_client.expire(key, self.window_size)
                return True
            else:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("rate_limiter", "limit_exceeded", {
                        "identifier": identifier,
                        "current_usage": current_usage,
                        "limit": self.limit_per_second
                    })
                else:
                    logger.warning(f"Rate limit exceeded for {identifier}: {current_usage}/{self.limit_per_second}")
                return False
                
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("rate_limiter", e, {
                    "operation": "is_allowed",
                    "identifier": identifier
                })
            else:
                logger.error(f"Error verificando rate limit: {str(e)}")
            return False

class WhatsAppAPI:
    """API principal para integración con WhatsApp Business API"""
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        self.rate_limiter = RateLimiter()
        self._setup_logging()
    
    def _setup_logging(self):
        """Configurar logging detallado"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if whatsapp_settings.enable_detailed_logging and ADVANCED_LOGGING_AVAILABLE:
                # Usar logging avanzado
                logging_manager.configure_logging(
                    log_level=whatsapp_settings.log_level.upper(),
                    log_file=whatsapp_settings.log_file_path or "logs/whatsapp/whatsapp.log",
                    enable_console=True,
                    enable_file=True,
                    enable_elk=True
                )
                logger.info("Logging avanzado configurado para WhatsApp API")
            elif whatsapp_settings.enable_detailed_logging:
                # Configurar nivel de log tradicional
                log_level = getattr(logging, whatsapp_settings.log_level.upper(), logging.INFO)
                logger.setLevel(log_level)
                
                # Configurar handler para archivo
                log_file = whatsapp_settings.log_file_path or "logs/whatsapp/whatsapp.log"
                
                # Crear directorio si no existe
                import os
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                
                # Configurar file handler
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(log_level)
                
                # Configurar formatter
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(formatter)
                
                # Agregar handler al logger
                logger.addHandler(file_handler)
                
                logger.info(f"Logging WhatsApp configurado en nivel {log_level} hacia {log_file}")
            
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("whatsapp_api", e, {
                    "operation": "_setup_logging",
                    "error_type": "configuration_error"
                })
            else:
                logger.error(f"Error configurando logging WhatsApp: {str(e)}")
    
    @log_whatsapp_event("send_template_message")
    @handle_whatsapp_errors("whatsapp_api")
    def send_template_message(self, recipient_phone, template_name, template_data=None, language="es"):
        """Enviar mensaje basado en plantilla"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "send_template_message",
                    recipient=recipient_phone,
                    template=template_name,
                    metadata={
                        "api_method": "send_template_message",
                        "language": language
                    }
                )
            
            # Obtener configuración
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": "WhatsApp no está habilitado"}
                    )
                return {"success": False, "error": "WhatsApp no está habilitado"}
            
            # Verificar rate limiting
            if not self.rate_limiter.is_allowed(recipient_phone):
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": "Rate limit excedido"}
                    )
                return {"success": False, "error": "Rate limit excedido"}
            
            # Obtener plantilla
            template_content = getattr(whatsapp_settings, f"{template_name}_template", "")
            if not template_content:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": f"Plantilla {template_name} no configurada"}
                    )
                return {"success": False, "error": f"Plantilla {template_name} no configurada"}
            
            # Procesar variables de plantilla
            processed_content = self._process_template_variables(template_content, template_data)
            
            # Preparar payload
            payload = {
                "messaging_product": "whatsapp",
                "to": f"whatsapp:{whatsapp_settings.phone_number_id}",
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language
                    },
                    "components": [
                        {
                            "type": "body",
                            "text": processed_content
                        }
                    ]
                }
            }
            
            # Enviar mensaje
            headers = {
                "Authorization": f"Bearer {whatsapp_settings.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"https://graph.facebook.com/v18.0/{whatsapp_settings.phone_number_id}/messages",
                headers=headers,
                json=payload,
                timeout=whatsapp_settings.message_timeout
            )
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            # Procesar respuesta
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id")
                
                # Registrar mensaje enviado con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_whatsapp_message({
                        "message_id": message_id,
                        "template_name": template_name,
                        "to": recipient_phone,
                        "type": "template"
                    }, "sent", performance_metrics={
                        "response_time_ms": response_time,
                        "api_endpoint": f"/{whatsapp_settings.phone_number_id}/messages"
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "messages_sent": 1,
                            "templates_used": 1
                        }
                    )
                else:
                    self._log_message("sent", recipient_phone, template_name, processed_content, message_id)
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "response": result
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_whatsapp_message({
                        "message_id": None,
                        "template_name": template_name,
                        "to": recipient_phone,
                        "type": "template"
                    }, "failed", error_details={
                        "error_type": "api_error",
                        "error_message": error_msg,
                        "status_code": response.status_code
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "api_error",
                            "error_message": error_msg,
                            "status_code": response.status_code
                        }
                    )
                else:
                    self._log_message("failed", recipient_phone, template_name, processed_content, None, error_msg)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = str(e)
            response_time = (time.time() - start_time) * 1000
            
            # Registrar excepción con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("whatsapp_api", e, {
                    "operation": "send_template_message",
                    "recipient": recipient_phone,
                    "template": template_name,
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": error_msg
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            else:
                self._log_message("error", recipient_phone, template_name, "", None, error_msg)
            
            return {"success": False, "error": error_msg}
    
    def _process_template_variables(self, template_content, template_data):
        """Procesar variables en plantilla"""
        if not template_data:
            return template_content
        
        try:
            # Convertir string a diccionario si es necesario
            if isinstance(template_data, str):
                template_data = json.loads(template_data)
            
            # Reemplazar variables
            processed_content = template_content
            for key, value in template_data.items():
                processed_content = processed_content.replace(f"{{{key}}}", str(value))
            
            return processed_content
            
        except Exception as e:
            logger.error(f"Error procesando variables de plantilla: {str(e)}")
            return template_content
    
    def _log_message(self, status, recipient_phone, template_name, content, message_id=None, error=None):
        """Registrar mensaje en base de datos y logs"""
        try:
            # Registrar en base de datos
            if status == "sent":
                message_doc = frappe.new_doc("WhatsApp Message")
                message_doc.message_type = "Outgoing"
                message_doc.direction = "Outbound"
                message_doc.recipient_phone = recipient_phone
                message_doc.message_content = content
                message_doc.template_name = template_name
                message_doc.template_used = 1
                message_doc.wa_message_id = message_id
                message_doc.status = "Sent"
                message_doc.sent_timestamp = datetime.now()
                message_doc.source = "KREO CRM"
                message_doc.campaign_name = "KREO Automatización"
                message_doc.insert()
            
            # Registrar en logs con logging avanzado
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "recipient": recipient_phone,
                "template": template_name,
                "message_id": message_id,
                "error": error
            }
            
            if ADVANCED_LOGGING_AVAILABLE:
                if status == "sent":
                    logging_manager.log_whatsapp_message({
                        "message_id": message_id,
                        "template_name": template_name,
                        "to": recipient_phone,
                        "type": "template" if template_name != "custom" else "text"
                    }, "sent", metadata=log_data)
                elif status == "failed":
                    logging_manager.log_whatsapp_message({
                        "message_id": message_id,
                        "template_name": template_name,
                        "to": recipient_phone,
                        "type": "template" if template_name != "custom" else "text"
                    }, "failed", error_details={"error_message": error}, metadata=log_data)
                elif status == "error":
                    logging_manager.log_error("whatsapp_api", Exception(error), {
                        "operation": "_log_message",
                        "status": status,
                        "recipient": recipient_phone,
                        "template": template_name
                    })
            else:
                if error:
                    logger.error(f"WhatsApp {status}: {json.dumps(log_data)}")
                else:
                    logger.info(f"WhatsApp {status}: {json.dumps(log_data)}")
                
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("whatsapp_api", e, {
                    "operation": "_log_message",
                    "status": status,
                    "recipient": recipient_phone,
                    "template": template_name
                })
            else:
                logger.error(f"Error registrando mensaje: {str(e)}")
    
    @log_whatsapp_event("send_custom_message")
    @handle_whatsapp_errors("whatsapp_api")
    @self.circuit_breaker
    def send_custom_message(self, recipient_phone, message_content):
        """Enviar mensaje personalizado"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "send_custom_message",
                    recipient=recipient_phone,
                    content_type="text",
                    metadata={
                        "api_method": "send_custom_message",
                        "content_length": len(message_content)
                    }
                )
            
            # Obtener configuración
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": "WhatsApp no está habilitado"}
                    )
                return {"success": False, "error": "WhatsApp no está habilitado"}
            
            # Verificar rate limiting
            if not self.rate_limiter.is_allowed(recipient_phone):
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": "Rate limit excedido"}
                    )
                return {"success": False, "error": "Rate limit excedido"}
            
            # Preparar payload
            payload = {
                "messaging_product": "whatsapp",
                "to": f"whatsapp:{whatsapp_settings.phone_number_id}",
                "type": "text",
                "text": message_content
            }
            
            # Enviar mensaje
            headers = {
                "Authorization": f"Bearer {whatsapp_settings.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"https://graph.facebook.com/v18.0/{whatsapp_settings.phone_number_id}/messages",
                headers=headers,
                json=payload,
                timeout=whatsapp_settings.message_timeout
            )
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            # Procesar respuesta
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id")
                
                # Registrar mensaje enviado con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_whatsapp_message({
                        "message_id": message_id,
                        "template_name": None,
                        "to": recipient_phone,
                        "type": "text"
                    }, "sent", performance_metrics={
                        "response_time_ms": response_time,
                        "api_endpoint": f"/{whatsapp_settings.phone_number_id}/messages"
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "messages_sent": 1,
                            "content_type": "text"
                        }
                    )
                else:
                    self._log_message("sent", recipient_phone, "custom", message_content, message_id)
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "response": result
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_whatsapp_message({
                        "message_id": None,
                        "template_name": None,
                        "to": recipient_phone,
                        "type": "text"
                    }, "failed", error_details={
                        "error_type": "api_error",
                        "error_message": error_msg,
                        "status_code": response.status_code
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "api_error",
                            "error_message": error_msg,
                            "status_code": response.status_code
                        }
                    )
                else:
                    self._log_message("failed", recipient_phone, "custom", message_content, None, error_msg)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = str(e)
            response_time = (time.time() - start_time) * 1000
            
            # Registrar excepción con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("whatsapp_api", e, {
                    "operation": "send_custom_message",
                    "recipient": recipient_phone,
                    "content_length": len(message_content),
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": error_msg
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            else:
                self._log_message("error", recipient_phone, "custom", message_content, None, error_msg)
            
            return {"success": False, "error": error_msg}
    
    @log_whatsapp_event("get_message_status")
    @handle_whatsapp_errors("whatsapp_api")
    def get_message_status(self, message_id):
        """Obtener estado de mensaje"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "get_message_status",
                    message_id=message_id,
                    metadata={
                        "api_method": "get_message_status"
                    }
                )
            
            # Obtener configuración
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={"error": "WhatsApp no está habilitado"}
                    )
                return {"success": False, "error": "WhatsApp no está habilitado"}
            
            # Preparar headers
            headers = {
                "Authorization": f"Bearer {whatsapp_settings.access_token}",
                "Content-Type": "application/json"
            }
            
            # Consultar estado
            response = requests.get(
                f"https://graph.facebook.com/v18.0/{message_id}",
                headers=headers,
                timeout=30
            )
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                
                # Registrar operación exitosa con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("whatsapp_api", "message_status_retrieved", {
                        "message_id": message_id,
                        "status": "success"
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "status_checks": 1
                        }
                    )
                
                return {
                    "success": True,
                    "data": result
                }
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("whatsapp_api", "message_status_failed", {
                        "message_id": message_id,
                        "status": "error",
                        "error_message": error_msg,
                        "status_code": response.status_code
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "api_error",
                            "error_message": error_msg,
                            "status_code": response.status_code
                        }
                    )
                
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = str(e)
            response_time = (time.time() - start_time) * 1000
            
            # Registrar excepción con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("whatsapp_api", e, {
                    "operation": "get_message_status",
                    "message_id": message_id,
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": error_msg
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            return {
                "success": False,
                "error": error_msg
            }

# Instancia global de la API
whatsapp_api = WhatsAppAPI()