# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
import requests
import logging
from datetime import datetime
from functools import wraps
import time

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event,
        handle_whatsapp_errors, get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
    logger = get_logger("webhook_config")
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible")

# Configuración de logging
logger = logging.getLogger(__name__)

def require_whatsapp_enabled(func):
    """Decorador para verificar que WhatsApp esté habilitado"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        if not whatsapp_settings.enabled:
            return {"success": False, "error": "WhatsApp no está habilitado"}
        return func(*args, **kwargs)
    return wrapper

def validate_webhook_security(func):
    """Decorador para validar seguridad de webhooks"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Verificar que la solicitud venga de Meta
            request = frappe.request
            if not request:
                return {"success": False, "error": "Solicitud no válida"}
            
            # Verificar HTTPS
            if not request.is_https:
                logger.warning("Webhook recibido sin HTTPS")
                return {"success": False, "error": "Conexión no segura"}
            
            # Verificar IP de Meta (puede ser expandido con IPs reales)
            # Por ahora solo verificamos el formato del payload
            if request.get_data():
                try:
                    data = json.loads(request.get_data())
                    if not isinstance(data, dict):
                        return {"success": False, "error": "Formato de datos inválido"}
                except json.JSONDecodeError:
                    return {"success": False, "error": "Datos JSON inválidos"}
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en validación de seguridad: {str(e)}")
            return {"success": False, "error": "Error de validación"}
    return wrapper

class WebhookConfig:
    """Gestión de configuración y registro de webhooks para WhatsApp"""
    
    def __init__(self):
        self.whatsapp_settings = None
        self._load_settings()
    
    def _load_settings(self):
        """Cargar configuración de WhatsApp"""
        try:
            self.whatsapp_settings = frappe.get_single("WhatsApp Settings")
        except Exception as e:
            logger.error(f"Error cargando configuración de WhatsApp: {str(e)}")
            raise
    
    @require_whatsapp_enabled
    @log_whatsapp_event("webhook_registration")
    @handle_whatsapp_errors("webhook_config")
    def register_webhook(self, webhook_url=None, verify_token=None):
        """Registrar webhook con Meta Business API"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "webhook_registration",
                    metadata={
                        "operation": "register_webhook",
                        "has_custom_url": bool(webhook_url),
                        "has_custom_token": bool(verify_token)
                    }
                )
            
            if not webhook_url:
                webhook_url = self._get_default_webhook_url()
            
            if not verify_token:
                verify_token = self.whatsapp_settings.webhook_verify_token
            
            # Validar URL
            if not self._validate_webhook_url(webhook_url):
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("webhook_config", "invalid_webhook_url", {
                        "status": "error",
                        "error_type": "invalid_url",
                        "webhook_url": webhook_url[:20] + "..." if webhook_url else "empty"
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "invalid_url",
                            "webhook_url": webhook_url[:20] + "..." if webhook_url else "empty"
                        }
                    )
                
                return {"success": False, "error": "URL de webhook no válida"}
            
            # Registrar webhook en Meta Business API
            headers = {
                "Authorization": f"Bearer {self.whatsapp_settings.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "webhook_url": webhook_url,
                "verify_token": verify_token,
                "fields": ["messages", "status", "errors"]
            }
            
            response = requests.post(
                f"https://graph.facebook.com/v18.0/{self.whatsapp_settings.phone_number_id}/subscribed_apps",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                # Actualizar configuración local
                self.whatsapp_settings.webhook_url = webhook_url
                self.whatsapp_settings.webhook_registered = True
                self.whatsapp_settings.webhook_registration_date = datetime.now()
                self.whatsapp_settings.save()
                
                # Registrar operación exitosa con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    response_time = (time.time() - start_time) * 1000
                    logging_manager.log_event("webhook_config", "webhook_registration_success", {
                        "status": "success",
                        "webhook_url": webhook_url,
                        "has_custom_url": bool(webhook_url),
                        "registration_date": self.whatsapp_settings.webhook_registration_date.isoformat()
                    }, performance_metrics={
                        "response_time_ms": response_time,
                        "api_response_time_ms": response.elapsed.total_seconds() * 1000
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "webhooks_registered": 1
                        },
                        performance_metrics={
                            "response_time_ms": response_time,
                            "api_response_time_ms": response.elapsed.total_seconds() * 1000
                        }
                    )
                
                logger.info(f"Webhook registrado exitosamente: {webhook_url}")
                
                return {
                    "success": True,
                    "message": "Webhook registrado exitosamente",
                    "webhook_url": webhook_url,
                    "registration_date": self.whatsapp_settings.webhook_registration_date
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    response_time = (time.time() - start_time) * 1000
                    logging_manager.log_event("webhook_config", "webhook_registration_failed", {
                        "status": "error",
                        "error_type": "api_error",
                        "http_status": response.status_code,
                        "error_message": error_msg,
                        "webhook_url": webhook_url
                    }, performance_metrics={
                        "response_time_ms": response_time,
                        "api_response_time_ms": response.elapsed.total_seconds() * 1000
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "api_error",
                            "http_status": response.status_code,
                            "error_message": error_msg
                        },
                        performance_metrics={
                            "response_time_ms": response_time,
                            "api_response_time_ms": response.elapsed.total_seconds() * 1000
                        }
                    )
                
                logger.error(f"Error registrando webhook: {error_msg}")
                return {
                    "success": False,
                    "error": f"Error {response.status_code}: {error_msg}"
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("webhook_config", e, {
                    "operation": "register_webhook",
                    "correlation_id": correlation_id,
                    "webhook_url": webhook_url
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Excepción registrando webhook: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    @require_whatsapp_enabled
    @log_whatsapp_event("webhook_unregistration")
    @handle_whatsapp_errors("webhook_config")
    def unregister_webhook(self):
        """Desregistrar webhook de Meta Business API"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "webhook_unregistration",
                    metadata={
                        "operation": "unregister_webhook",
                        "current_webhook_url": self.whatsapp_settings.webhook_url
                    }
                )
            
            headers = {
                "Authorization": f"Bearer {self.whatsapp_settings.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.delete(
                f"https://graph.facebook.com/v18.0/{self.whatsapp_settings.phone_number_id}/subscribed_apps",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                # Actualizar configuración local
                previous_url = self.whatsapp_settings.webhook_url
                self.whatsapp_settings.webhook_url = ""
                self.whatsapp_settings.webhook_registered = False
                self.whatsapp_settings.webhook_registration_date = None
                self.whatsapp_settings.save()
                
                # Registrar operación exitosa con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    response_time = (time.time() - start_time) * 1000
                    logging_manager.log_event("webhook_config", "webhook_unregistration_success", {
                        "status": "success",
                        "previous_webhook_url": previous_url,
                        "unregistration_date": datetime.now().isoformat()
                    }, performance_metrics={
                        "response_time_ms": response_time,
                        "api_response_time_ms": response.elapsed.total_seconds() * 1000
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "webhooks_unregistered": 1
                        },
                        performance_metrics={
                            "response_time_ms": response_time,
                            "api_response_time_ms": response.elapsed.total_seconds() * 1000
                        }
                    )
                
                logger.info("Webhook desregistrado exitosamente")
                
                return {
                    "success": True,
                    "message": "Webhook desregistrado exitosamente"
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    response_time = (time.time() - start_time) * 1000
                    logging_manager.log_event("webhook_config", "webhook_unregistration_failed", {
                        "status": "error",
                        "error_type": "api_error",
                        "http_status": response.status_code,
                        "error_message": error_msg,
                        "current_webhook_url": self.whatsapp_settings.webhook_url
                    }, performance_metrics={
                        "response_time_ms": response_time,
                        "api_response_time_ms": response.elapsed.total_seconds() * 1000
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "api_error",
                            "http_status": response.status_code,
                            "error_message": error_msg
                        },
                        performance_metrics={
                            "response_time_ms": response_time,
                            "api_response_time_ms": response.elapsed.total_seconds() * 1000
                        }
                    )
                
                logger.error(f"Error desregistrando webhook: {error_msg}")
                return {
                    "success": False,
                    "error": f"Error {response.status_code}: {error_msg}"
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("webhook_config", e, {
                    "operation": "unregister_webhook",
                    "correlation_id": correlation_id,
                    "current_webhook_url": self.whatsapp_settings.webhook_url
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Excepción desregistrando webhook: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def verify_webhook_callback(self, request_data):
        """Verificar callback de webhook de Meta"""
        try:
            # Verificar que sea un callback de verificación
            if "hub.mode" in request_data and "hub.verify_token" in request_data:
                mode = request_data.get("hub.mode")
                verify_token = request_data.get("hub.verify_token")
                challenge = request_data.get("hub.challenge")
                
                if mode == "subscribe" and verify_token == self.whatsapp_settings.webhook_verify_token:
                    logger.info("Callback de verificación de webhook validado")
                    return {
                        "success": True,
                        "challenge": challenge
                    }
                else:
                    logger.warning("Callback de verificación inválido")
                    return {
                        "success": False,
                        "error": "Token de verificación inválido"
                    }
            
            return {"success": True, "message": "Callback válido"}
            
        except Exception as e:
            logger.error(f"Error verificando callback de webhook: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    @validate_webhook_security
    @log_whatsapp_event("webhook_event_processing")
    @handle_whatsapp_errors("webhook_config")
    def process_webhook_event(self, webhook_data):
        """Procesar eventos de webhook de WhatsApp"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "webhook_event_processing",
                    metadata={
                        "operation": "process_webhook_event",
                        "data_size": len(json.dumps(webhook_data)) if webhook_data else 0
                    }
                )
            
            # Registrar evento de webhook
            self._log_webhook_event(webhook_data)
            
            # Verificar si es un evento de Meta
            if not self._is_valid_meta_event(webhook_data):
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("webhook_config", "invalid_meta_event", {
                        "status": "error",
                        "error_type": "invalid_meta_event",
                        "object_type": webhook_data.get("object") if webhook_data else "none"
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "invalid_meta_event",
                            "object_type": webhook_data.get("object") if webhook_data else "none"
                        }
                    )
                
                return {"success": False, "error": "Evento no válido de Meta"}
            
            # Procesar según el tipo de evento
            object_type = webhook_data.get("object")
            entries = webhook_data.get("entry", [])
            
            if object_type == "whatsapp_business_account":
                result = self._process_whatsapp_events(entries)
            elif object_type == "page":
                result = self._process_page_events(entries)
            else:
                # Registrar advertencia con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("webhook_config", "unknown_object_type", {
                        "status": "warning",
                        "object_type": object_type,
                        "entry_count": len(entries)
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "warning",
                        warning_details={
                            "object_type": object_type,
                            "message": "Tipo de objeto desconocido"
                        }
                    )
                
                logger.warning(f"Tipo de objeto desconocido: {object_type}")
                return {"success": False, "error": "Tipo de objeto desconocido"}
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE and result.get("success"):
                response_time = (time.time() - start_time) * 1000
                logging_manager.log_event("webhook_config", "webhook_event_processed", {
                    "status": "success",
                    "object_type": object_type,
                    "entry_count": len(entries),
                    "processed_count": result.get("processed", 0),
                    "error_count": len(result.get("errors", []))
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "webhook_events_processed": result.get("processed", 0),
                        "webhook_events_with_errors": len(result.get("errors", []))
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
                
            return result
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("webhook_config", e, {
                    "operation": "process_webhook_event",
                    "correlation_id": correlation_id,
                    "object_type": webhook_data.get("object") if webhook_data else "none"
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error procesando evento de webhook: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_whatsapp_events(self, entries):
        """Procesar eventos de WhatsApp Business"""
        try:
            processed_count = 0
            errors = []
            
            for entry in entries:
                changes = entry.get("changes", [])
                
                for change in changes:
                    value = change.get("value", {})
                    field = change.get("field")
                    
                    if field == "messages":
                        result = self._process_message_event(value)
                        if result.get("success"):
                            processed_count += 1
                        else:
                            errors.append(result.get("error", "Error desconocido"))
                    
                    elif field == "statuses":
                        result = self._process_status_event(value)
                        if result.get("success"):
                            processed_count += 1
                        else:
                            errors.append(result.get("error", "Error desconocido"))
                    
                    elif field == "errors":
                        result = self._process_error_event(value)
                        if result.get("success"):
                            processed_count += 1
                        else:
                            errors.append(result.get("error", "Error desconocido"))
            
            return {
                "success": True,
                "processed": processed_count,
                "errors": errors,
                "total": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error procesando eventos de WhatsApp: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_page_events(self, entries):
        """Procesar eventos de página (legacy)"""
        try:
            # Para compatibilidad con versiones anteriores
            processed_count = 0
            
            for entry in entries:
                messaging = entry.get("messaging", [])
                
                for message_data in messaging:
                    if "message" in message_data:
                        result = self._process_message_event(message_data)
                        if result.get("success"):
                            processed_count += 1
                    
                    elif "delivery" in message_data:
                        result = self._process_delivery_event(message_data)
                        if result.get("success"):
                            processed_count += 1
            
            return {
                "success": True,
                "processed": processed_count,
                "total": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error procesando eventos de página: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_message_event(self, message_data):
        """Procesar evento de mensaje"""
        try:
            # Enviar a la cola de procesamiento
            from kreo_whats2.kreo_whats2.api.queue_processor import QueueProcessor
            queue_processor = QueueProcessor()
            
            result = queue_processor.add_message_to_queue(message_data, "message")
            
            if result.get("success"):
                logger.info(f"Mensaje agregado a cola: {message_data.get('id', 'unknown')}")
            else:
                logger.error(f"Error agregando mensaje a cola: {result.get('error', 'Error desconocido')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error procesando evento de mensaje: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_status_event(self, status_data):
        """Procesar evento de estado"""
        try:
            # Enviar a la cola de procesamiento
            from kreo_whats2.kreo_whats2.api.queue_processor import QueueProcessor
            queue_processor = QueueProcessor()
            
            result = queue_processor.add_message_to_queue(status_data, "status")
            
            if result.get("success"):
                logger.info(f"Estado agregado a cola: {status_data.get('id', 'unknown')}")
            else:
                logger.error(f"Error agregando estado a cola: {result.get('error', 'Error desconocido')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error procesando evento de estado: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_error_event(self, error_data):
        """Procesar evento de error"""
        try:
            # Registrar error
            self._log_webhook_error(error_data)
            
            logger.warning(f"Evento de error recibido: {error_data}")
            
            return {
                "success": True,
                "message": "Error registrado"
            }
            
        except Exception as e:
            logger.error(f"Error procesando evento de error: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _process_delivery_event(self, delivery_data):
        """Procesar evento de entrega"""
        try:
            # Enviar a la cola de procesamiento
            from kreo_whats2.kreo_whats2.api.queue_processor import QueueProcessor
            queue_processor = QueueProcessor()
            
            result = queue_processor.add_message_to_queue(delivery_data, "delivery")
            
            if result.get("success"):
                logger.info(f"Entrega agregada a cola: {delivery_data.get('id', 'unknown')}")
            else:
                logger.error(f"Error agregando entrega a cola: {result.get('error', 'Error desconocido')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error procesando evento de entrega: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }
    
    def _get_default_webhook_url(self):
        """Obtener URL de webhook por defecto"""
        if self.whatsapp_settings.ngrok_url:
            return f"{self.whatsapp_settings.ngrok_url}/api/method/kreo_whats2.webhook"
        else:
            return "https://kreo.localhost/api/method/kreo_whats2.webhook"
    
    def _validate_webhook_url(self, url):
        """Validar formato y seguridad de URL de webhook"""
        try:
            from urllib.parse import urlparse
            
            # Verificar que sea HTTPS
            parsed = urlparse(url)
            if parsed.scheme != "https":
                logger.error("URL de webhook debe usar HTTPS")
                return False
            
            # Verificar que tenga host y path
            if not parsed.netloc or not parsed.path:
                logger.error("URL de webhook inválida")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validando URL de webhook: {str(e)}")
            return False
    
    def _is_valid_meta_event(self, data):
        """Verificar si es un evento válido de Meta"""
        required_fields = ["object", "entry"]
        
        for field in required_fields:
            if field not in data:
                return False
        
        return True
    
    def _log_webhook_event(self, data):
        """Registrar evento de webhook"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": data.get("object", "unknown"),
                "entry_count": len(data.get("entry", [])),
                "processed": True
            }
            
            logger.info(f"Webhook event: {json.dumps(log_entry)}")
            
        except Exception as e:
            logger.error(f"Error registrando evento de webhook: {str(e)}")
    
    def _log_webhook_error(self, error_data):
        """Registrar error de webhook"""
        try:
            error_entry = {
                "timestamp": datetime.now().isoformat(),
                "error_type": "webhook_error",
                "error_data": error_data,
                "severity": "warning"
            }
            
            logger.warning(f"Webhook error: {json.dumps(error_entry)}")
            
        except Exception as e:
            logger.error(f"Error registrando error de webhook: {str(e)}")
    
    @frappe.whitelist()
    @log_whatsapp_event("webhook_status_retrieval")
    @handle_whatsapp_errors("webhook_config")
    def get_webhook_status(self):
        """Obtener estado del webhook"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "webhook_status_retrieval",
                    metadata={
                        "operation": "get_webhook_status",
                        "purpose": "status_check"
                    }
                )
            
            status_data = {
                "webhook_registered": self.whatsapp_settings.webhook_registered,
                "webhook_url": self.whatsapp_settings.webhook_url,
                "registration_date": self.whatsapp_settings.webhook_registration_date,
                "verify_token_set": bool(self.whatsapp_settings.webhook_verify_token),
                "ngrok_active": bool(self.whatsapp_settings.ngrok_url)
            }
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                response_time = (time.time() - start_time) * 1000
                logging_manager.log_event("webhook_config", "webhook_status_retrieved", {
                    "status": "success",
                    "webhook_registered": status_data["webhook_registered"],
                    "verify_token_set": status_data["verify_token_set"],
                    "ngrok_active": status_data["ngrok_active"]
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "status_checks": 1
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
            
            return status_data
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("webhook_config", e, {
                    "operation": "get_webhook_status",
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error obteniendo estado de webhook: {str(e)}")
            return {"error": str(e)}

# Instancia global de configuración de webhooks
webhook_config = WebhookConfig()