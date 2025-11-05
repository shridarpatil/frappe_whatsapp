# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
import logging
from datetime import datetime
import time

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event,
        handle_whatsapp_errors, get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
    logger = get_logger("webhook_handler")
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible")

@frappe.whitelist(allow_guest=True)
@log_whatsapp_event("webhook")
@handle_whatsapp_errors("webhook_handler")
def webhook():
    """Manejar webhooks entrantes desde WhatsApp Business API"""
    start_time = time.time()
    correlation_id = None
    
    try:
        # Iniciar contexto de operación si está disponible el logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "webhook",
                method=frappe.request.method,
                metadata={
                    "operation": "webhook",
                    "component": "webhook_handler"
                }
            )
        
        # Verificar método
        if frappe.request.method not in ["POST", "GET"]:
            frappe.response.response_type = "json"
            frappe.response.status_code = 405
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_method", {
                    "status": "error",
                    "error_type": "invalid_method",
                    "method": frappe.request.method
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_method",
                        "method": frappe.request.method
                    }
                )
            
            return {"status": "error", "message": "Método no permitido"}
        
        # Manejar verificación de webhook (GET)
        if frappe.request.method == "GET":
            result = _handle_webhook_verification()
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "webhook_verification", {
                    "status": "success",
                    "method": "GET"
                }, performance_metrics={
                    "response_time_ms": (time.time() - start_time) * 1000
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "webhook_verifications": 1
                    },
                    performance_metrics={
                        "response_time_ms": (time.time() - start_time) * 1000
                    }
                )
            
            return result
        
        # Manejar eventos de webhook (POST)
        result = _handle_webhook_events()
        
        # Registrar operación exitosa con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_event("webhook_handler", "webhook_events_processed", {
                "status": "success",
                "method": "POST"
            }, performance_metrics={
                "response_time_ms": (time.time() - start_time) * 1000
            })
            
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={
                    "webhook_events": 1
                },
                performance_metrics={
                    "response_time_ms": (time.time() - start_time) * 1000
                }
            )
        
        return result
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        
        # Registrar error con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_error("webhook_handler", e, {
                "operation": "webhook",
                "method": frappe.request.method,
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
        
        logger.error(f"Error en webhook: {str(e)}")
        frappe.response.response_type = "json"
        frappe.response.status_code = 500
        return {"status": "error", "message": "Error interno del servidor"}

@log_whatsapp_event("webhook_verification")
@handle_whatsapp_errors("webhook_handler")
def _handle_webhook_verification():
    """Manejar verificación de webhook (GET request)"""
    start_time = time.time()
    correlation_id = None
    
    try:
        # Iniciar contexto de operación si está disponible el logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "webhook_verification",
                metadata={
                    "operation": "_handle_webhook_verification"
                }
            )
        
        # Obtener parámetros de verificación
        verify_token = frappe.request.args.get("hub.verify_token")
        challenge = frappe.request.args.get("hub.challenge")
        mode = frappe.request.args.get("hub.mode")
        
        if not all([verify_token, challenge, mode]):
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "missing_verification_params", {
                    "status": "error",
                    "error_type": "missing_parameters",
                    "has_token": bool(verify_token),
                    "has_challenge": bool(challenge),
                    "has_mode": bool(mode)
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "missing_parameters",
                        "missing_fields": [field for field, value in
                                         [("token", verify_token), ("challenge", challenge), ("mode", mode)]
                                         if not value]
                    }
                )
            
            return {"status": "error", "message": "Parámetros de verificación incompletos"}
        
        # Verificar token con configuración
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.webhook_verify_token:
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "webhook_not_configured", {
                    "status": "error",
                    "error_type": "not_configured"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "not_configured",
                        "message": "Webhook no configurado en settings"
                    }
                )
            
            return {"status": "error", "message": "Webhook no configurado"}
        
        if verify_token != whatsapp_settings.webhook_verify_token:
            frappe.response.response_type = "json"
            frappe.response.status_code = 403
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_verification_token", {
                    "status": "error",
                    "error_type": "invalid_token",
                    "provided_token": verify_token[:10] + "..." if verify_token else "empty"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_token",
                        "provided_token": verify_token[:10] + "..." if verify_token else "empty"
                    }
                )
            
            return {"status": "error", "message": "Token de verificación inválido"}
        
        if mode != "subscribe":
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_verification_mode", {
                    "status": "error",
                    "error_type": "invalid_mode",
                    "provided_mode": mode
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_mode",
                        "provided_mode": mode
                    }
                )
            
            return {"status": "error", "message": "Modo de verificación inválido"}
        
        # Verificación exitosa - responder con el challenge
        frappe.response.response_type = "text"
        frappe.response.status_code = 200
        
        # Registrar operación exitosa con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            response_time = (time.time() - start_time) * 1000
            logging_manager.log_event("webhook_handler", "webhook_verification_success", {
                "status": "success",
                "mode": mode
            }, performance_metrics={
                "response_time_ms": response_time
            })
            
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={
                    "verifications": 1
                },
                performance_metrics={
                    "response_time_ms": response_time
                }
            )
        
        return challenge
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        
        # Registrar error con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_error("webhook_handler", e, {
                "operation": "_handle_webhook_verification",
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
        
        logger.error(f"Error en verificación de webhook: {str(e)}")
        frappe.response.response_type = "json"
        frappe.response.status_code = 500
        return {"status": "error", "message": "Error interno del servidor"}

@log_whatsapp_event("webhook_events")
@handle_whatsapp_errors("webhook_handler")
def _handle_webhook_events():
    """Manejar eventos de webhook (POST request)"""
    start_time = time.time()
    correlation_id = None
    
    try:
        # Iniciar contexto de operación si está disponible el logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "webhook_events",
                metadata={
                    "operation": "_handle_webhook_events"
                }
            )
        
        # Obtener datos del webhook
        webhook_data = frappe.request.get_json()
        
        if not webhook_data:
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_webhook_data", {
                    "status": "error",
                    "error_type": "invalid_data"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_data",
                        "message": "Datos del webhook no válidos"
                    }
                )
            
            return {"status": "error", "message": "Datos del webhook no válidos"}
        
        # Verificar si es un webhook de WhatsApp válido
        object_type = webhook_data.get("object")
        if object_type not in ["whatsapp_business_account", "page"]:
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_webhook_object", {
                    "status": "error",
                    "error_type": "invalid_object",
                    "object_type": object_type
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_object",
                        "object_type": object_type
                    }
                )
            
            return {"status": "error", "message": "Tipo de objeto no válido"}
        
        # Procesar webhook usando la nueva configuración
        from kreo_whats2.kreo_whats2.api.webhook_config import webhook_config
        
        result = webhook_config.process_webhook_event(webhook_data)
        
        # Responder a WhatsApp
        frappe.response.response_type = "json"
        frappe.response.status_code = 200
        
        # Calcular tiempo de respuesta
        response_time = (time.time() - start_time) * 1000
        
        if result.get("success"):
            response_data = {
                "status": "success",
                "message": "Webhook procesado exitosamente",
                "processed": result.get("processed", 0)
            }
            
            # Agregar información de errores si existen
            if result.get("errors"):
                response_data["errors"] = result.get("errors")
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "webhook_events_success", {
                    "status": "success",
                    "object_type": object_type,
                    "processed": result.get("processed", 0),
                    "errors_count": len(result.get("errors", []))
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
                
            return response_data
        else:
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "webhook_processing_failed", {
                    "status": "error",
                    "error_type": "processing_error",
                    "object_type": object_type,
                    "error_message": result.get("error", "Error procesando webhook")
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "processing_error",
                        "error_message": result.get("error", "Error procesando webhook")
                    }
                )
            
            return {
                "status": "error",
                "message": result.get("error", "Error procesando webhook")
            }
            
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        
        # Registrar error con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_error("webhook_handler", e, {
                "operation": "_handle_webhook_events",
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
        
        logger.error(f"Error procesando eventos de webhook: {str(e)}")
        frappe.response.response_type = "json"
        frappe.response.status_code = 500
        return {"status": "error", "message": "Error interno del servidor"}

@frappe.whitelist()
@log_whatsapp_event("webhook_verification_legacy")
@handle_whatsapp_errors("webhook_handler")
def verify_webhook():
    """Verificar webhook para configuración inicial (legacy endpoint)"""
    start_time = time.time()
    correlation_id = None
    
    try:
        # Iniciar contexto de operación si está disponible el logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "webhook_verification_legacy",
                metadata={
                    "operation": "verify_webhook",
                    "endpoint": "legacy"
                }
            )
        
        # Obtener token de verificación
        verify_token = frappe.request.args.get("hub.verify_token")
        
        if not verify_token:
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "missing_verify_token_legacy", {
                    "status": "error",
                    "error_type": "missing_token"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "missing_token",
                        "message": "Token de verificación no proporcionado en endpoint legacy"
                    }
                )
            
            return {"status": "error", "message": "Token de verificación no proporcionado"}
        
        # Obtener configuración
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.webhook_verify_token:
            frappe.response.response_type = "json"
            frappe.response.status_code = 400
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "webhook_not_configured_legacy", {
                    "status": "error",
                    "error_type": "not_configured"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "not_configured",
                        "message": "Webhook no configurado en settings (endpoint legacy)"
                    }
                )
            
            return {"status": "error", "message": "Webhook no configurado"}
        
        # Verificar token
        if verify_token != whatsapp_settings.webhook_verify_token:
            frappe.response.response_type = "json"
            frappe.response.status_code = 403
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("webhook_handler", "invalid_verify_token_legacy", {
                    "status": "error",
                    "error_type": "invalid_token",
                    "provided_token": verify_token[:10] + "..." if verify_token else "empty"
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": "invalid_token",
                        "provided_token": verify_token[:10] + "..." if verify_token else "empty"
                    }
                )
            
            return {"status": "error", "message": "Token de verificación inválido"}
        
        # Responder con éxito
        frappe.response.response_type = "json"
        frappe.response.status_code = 200
        
        # Registrar operación exitosa con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            response_time = (time.time() - start_time) * 1000
            logging_manager.log_event("webhook_handler", "webhook_verification_legacy_success", {
                "status": "success",
                "endpoint": "legacy"
            }, performance_metrics={
                "response_time_ms": response_time
            })
            
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={
                    "legacy_verifications": 1
                },
                performance_metrics={
                    "response_time_ms": response_time
                }
            )
        
        return {"status": "success", "message": "Webhook verificado exitosamente"}
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        
        # Registrar error con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_error("webhook_handler", e, {
                "operation": "verify_webhook_legacy",
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
        
        logger.error(f"Error en verificación de webhook legacy: {str(e)}")
        frappe.response.response_type = "json"
        frappe.response.status_code = 500
        return {"status": "error", "message": "Error interno del servidor"}

@frappe.whitelist()
@log_whatsapp_event("webhook_status_check")
@handle_whatsapp_errors("webhook_handler")
def get_webhook_status():
    """Obtener estado del webhook (para debugging)"""
    start_time = time.time()
    correlation_id = None
    
    try:
        # Iniciar contexto de operación si está disponible el logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "webhook_status_check",
                metadata={
                    "operation": "get_webhook_status",
                    "purpose": "debugging"
                }
            )
        
        from kreo_whats2.kreo_whats2.api.webhook_config import webhook_config
        
        status = webhook_config.get_webhook_status()
        
        frappe.response.response_type = "json"
        frappe.response.status_code = 200
        
        # Registrar operación exitosa con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            response_time = (time.time() - start_time) * 1000
            logging_manager.log_event("webhook_handler", "webhook_status_retrieved", {
                "status": "success",
                "has_webhook_config": bool(status.get("webhook_config")),
                "has_verification_token": bool(status.get("verification_token")),
                "last_updated": status.get("last_updated")
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
        
        return {
            "status": "success",
            "data": status
        }
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        
        # Registrar error con logging avanzado
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.log_error("webhook_handler", e, {
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
        frappe.response.response_type = "json"
        frappe.response.status_code = 500
        return {"status": "error", "message": "Error interno del servidor"}