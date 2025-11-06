# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _

# Importar logging avanzado con manejo de errores robusto
try:
    from kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event, handle_whatsapp_errors,
        log_security_event, get_logger, log_whatsapp_message
    )
    ADVANCED_LOGGING_AVAILABLE = True
    print("✅ Logging avanzado disponible en hooks")
except ImportError as e:
    ADVANCED_LOGGING_AVAILABLE = False
    print(f"⚠️  Advertencia: Logging avanzado no disponible en hooks - {e}")

# Importar decoradores de logging con manejo de fallback
if ADVANCED_LOGGING_AVAILABLE:
    from kreo_whats2.utils.logging_manager import (
        log_whatsapp_event, handle_whatsapp_errors
    )
else:
    # Fallback decorators que no hacen nada si logging no está disponible
    def log_whatsapp_event(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def handle_whatsapp_errors(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Hooks de automatización para WhatsApp
app_title = "KREO WhatsApp Integration"
app_publisher = "KREO Colombia"
app_description = "Integración avanzada de WhatsApp para KREO Colombia con logging estructurado"
app_icon = "octicon octicon-comment-discussion"
app_color = "green"
app_email = "dev@kreo.one"
app_license = "MIT"
app_version = "1.0.7"

app_name = "kreo_whats2"

# Hooks de documentos con logging avanzado integrado con Frappe
doc_events = {
    "Sales Invoice": {
        "on_submit": "kreo_whats2.kreo_whats2.hooks.sales_invoice_on_submit",
        "on_cancel": "kreo_whats2.kreo_whats2.hooks.sales_invoice_on_cancel"
    },
    "Lead": {
        "after_insert": "kreo_whats2.kreo_whats2.hooks.lead_after_insert",
        "on_update": "kreo_whats2.kreo_whats2.hooks.lead_on_update"
    },
    "Payment Entry": {
        "on_submit": "kreo_whats2.kreo_whats2.hooks.payment_entry_on_submit"
    },
    "Customer": {
        "after_insert": "kreo_whats2.kreo_whats2.hooks.customer_after_insert"
    }
}

# Hooks de documentos adicionales para logging de eventos de Frappe
doc_events.update({
    "WhatsApp Settings": {
        "on_update": "kreo_whats2.kreo_whats2.hooks.whatsapp_settings_on_update",
        "validate": "kreo_whats2.kreo_whats2.hooks.whatsapp_settings_validate"
    },
    "WhatsApp Message": {
        "on_submit": "kreo_whats2.kreo_whats2.hooks.whatsapp_message_on_submit",
        "on_update": "kreo_whats2.kreo_whats2.hooks.whatsapp_message_on_update"
    },
    "WhatsApp Template": {
        "on_submit": "kreo_whats2.kreo_whats2.hooks.whatsapp_template_on_submit",
        "validate": "kreo_whats2.kreo_whats2.hooks.whatsapp_template_validate"
    }
})

# Hooks de programación de tareas (scheduler) con logging avanzado
scheduler_events = {
    "daily": [
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.send_payment_reminders",
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.send_invoice_reminders",
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.cleanup_old_messages"
    ],
    "hourly": [
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.process_whatsapp_queue",
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.health_check_whatsapp_service"
    ],
    "all": [
        "kreo_whats2.kreo_whats2.hooks.scheduler_hooks.update_whatsapp_stats"
    ]
}

# Hooks de API con logging avanzado - COMENTADO hasta que existan los módulos
# api_whitelist = [
#     "kreo_whats2.api.whatsapp_api.send_template_message",
#     "kreo_whats2.api.whatsapp_api.send_custom_message",
#     "kreo_whats2.api.whatsapp_api.get_message_status",
#     "kreo_whats2.api.webhook_handler.webhook",
#     "kreo_whats2.api.webhook_handler.verify_webhook",
# ]

# Hooks de permisos con logging - COMENTADO hasta que exista el módulo
# permission_query_conditions = {
#     "WhatsApp Message": "kreo_whats2.utils.permissions.has_whatsapp_access"
# }

# Hooks de configuración con logging
# override_doctype_class debe ser un diccionario de clases, no de strings
# override_doctype_class = {
#     "WhatsApp Settings": "kreo_whats2.overrides.whatsapp_settings_override.WhatsAppSettingsOverride",
#     "WhatsApp Message": "kreo_whats2.overrides.whatsapp_message_override.WhatsAppMessageOverride"
# }

# Hooks de UI con logging
doctype_js = {
    "WhatsApp Settings": "public/js/whatsapp_settings.js",
    "WhatsApp Message": "public/js/whatsapp_message.js"
}

# Hooks de eventos de Frappe con logging avanzado - COMENTADO hasta que las funciones estén listas
# before_request = "kreo_whats2.hooks.before_request"
# on_session_creation = "kreo_whats2.hooks.on_session_creation"
# on_logout = "kreo_whats2.hooks.on_logout"

# NOTA: template_customization NO es un hook válido de Frappe - ELIMINADO
# Las plantillas deben registrarse de otra manera

# Configuración de automatización de logging para eventos críticos
CRITICAL_EVENTS_CONFIG = {
    "security_events": [
        "authentication_failure",
        "unauthorized_access",
        "data_breach_attempt",
        "sensitive_operation",
        "whatsapp_settings_changed",
        "whatsapp_template_modified",
        "whatsapp_message_failed"
    ],
    "performance_thresholds": {
        "slow_operation_ms": 5000,
        "queue_backlog_threshold": 100,
        "error_rate_threshold": 0.1,
        "whatsapp_api_timeout": 30000
    },
    "business_metrics": {
        "messages_sent_threshold": 1000,
        "failure_rate_threshold": 0.05,
        "whatsapp_settings_validation_failed": 5
    },
    "frappe_events": [
        "doctype_validation_error",
        "permission_check_failed",
        "data_integrity_violation",
        "system_configuration_changed"
    ]
}

# Decoradores automáticos para hooks con logging avanzado
def auto_log_hook(operation_name: str, hook_type: str = "document"):
    """Decorador para automatizar logging en hooks"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not ADVANCED_LOGGING_AVAILABLE:
                return func(*args, **kwargs)
            
            correlation_id = None
            start_time = None
            
            try:
                # Iniciar contexto de operación
                start_time = logging_manager.start_operation_context(
                    operation_name,
                    hook_type=hook_type,
                    user=frappe.session.user if frappe.session else "system",
                    metadata={
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()) if kwargs else []
                    }
                )
                
                # Ejecutar función original
                result = func(*args, **kwargs)
                
                # Finalizar contexto con éxito
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        f"{hook_type}s_processed": 1
                    }
                )
                
                return result
                
            except Exception as e:
                # Registrar error y finalizar contexto
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                
                # Registrar error detallado
                log_error("hooks", e, {
                    "hook": operation_name,
                    "hook_type": hook_type,
                    "args": str(args),
                    "kwargs": str(kwargs)
                })
                raise
        return wrapper
    return decorator

# Funciones de hook con decoradores automáticos y logging avanzado
@auto_log_hook("sales_invoice_on_submit", "document")
def sales_invoice_on_submit(doc, method):
    """Hook para envío de factura con logging avanzado automático"""
    # Importar y ejecutar hook original
    from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import sales_invoice_on_submit as original_hook
    return original_hook(doc, method)

@auto_log_hook("lead_after_insert", "document")
def lead_after_insert(doc, method):
    """Hook para inserción de lead con logging avanzado automático"""
    # Importar y ejecutar hook original
    from kreo_whats2.kreo_whats2.hooks.lead_hooks import lead_after_insert as original_hook
    return original_hook(doc, method)

@auto_log_hook("payment_entry_on_submit", "document")
def payment_entry_on_submit(doc, method):
    """Hook para envío de pago con logging avanzado automático"""
    # Importar y ejecutar hook original
    from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import payment_entry_on_submit as original_hook
    return original_hook(doc, method)

@auto_log_hook("customer_after_insert", "document")
def customer_after_insert(doc, method):
    """Hook para inserción de cliente con logging avanzado automático"""
    # Importar y ejecutar hook original
    from kreo_whats2.kreo_whats2.hooks.lead_hooks import customer_after_insert as original_hook
    return original_hook(doc, method)

def lead_on_update(doc, method):
    """Hook para actualización de lead con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "lead_on_update",
                lead=doc.lead_name,
                company=doc.company_name,
                metadata={
                    "doctype": "Lead",
                    "operation": "on_update",
                    "changed_fields": doc.get_valid_dict().changed
                }
            )
        
        # Importar y ejecutar hook original
        from kreo_whats2.kreo_whats2.hooks.lead_hooks import lead_on_update as original_hook
        result = original_hook(doc, method)
        
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={
                    "leads_updated": 1
                }
            )
        
        return result
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("hooks", e, {
                "hook": "lead_on_update",
                "lead": doc.lead_name if 'doc' in locals() else "unknown"
            })
        raise

def sales_invoice_on_cancel(doc, method):
    """Hook para cancelación de factura con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "sales_invoice_on_cancel",
                invoice=doc.name,
                customer=doc.customer_name,
                amount=doc.grand_total,
                metadata={
                    "doctype": "Sales Invoice",
                    "operation": "on_cancel",
                    "cancel_reason": doc.get_formatted("reason_for_cancellation")
                }
            )
        
        # Importar y ejecutar hook original
        from kreo_whats2.kreo_whats2.hooks.template_automation_hooks import sales_invoice_on_cancel as original_hook
        result = original_hook(doc, method)
        
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={
                    "invoices_cancelled": 1
                }
            )
        
        return result
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("hooks", e, {
                "hook": "sales_invoice_on_cancel",
                "invoice": doc.name if 'doc' in locals() else "unknown"
            })
        raise

# Funciones de seguridad con logging estructurado
def log_security_hook(event_type: str, **kwargs):
    """Función para registrar eventos de seguridad en hooks"""
    if ADVANCED_LOGGING_AVAILABLE:
        security_context = {
            "event_type": event_type,
            "ip_address": kwargs.get("ip_address"),
            "user_agent": kwargs.get("user_agent"),
            "user": kwargs.get("user", frappe.session.user if frappe.session else "system"),
            "sensitive_operation": kwargs.get("sensitive_operation", False),
            "critical": kwargs.get("critical", False)
        }
        
        log_security_event(event_type, **security_context)

# Hook de permisos con logging de seguridad
def has_whatsapp_access(doctype, txt, searchfield, start, page_len, filters, reference_doctype, ignore_permissions=False):
    """Hook de permisos con logging de seguridad"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            # Registrar intento de acceso
            log_security_hook("permission_check",
                sensitive_operation=True,
                critical=False,
                metadata={
                    "doctype": doctype,
                    "user": frappe.session.user if frappe.session else "system",
                    "operation": "has_whatsapp_access"
                }
            )
        
        # Importar y ejecutar hook original
        from kreo_whats2.kreo_whats2.utils.permissions import has_whatsapp_access as original_hook
        result = original_hook(doctype, txt, searchfield, start, page_len, filters, reference_doctype, ignore_permissions)
        
        return result
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_security_hook("permission_error",
                sensitive_operation=True,
                critical=True,
                error_details={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
        raise

# Hook de configuración con logging
def whatsapp_settings_override(doctype, docname):
    """Hook de override con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("configuration", "INFO", "WhatsApp Settings override aplicado",
                operation="whatsapp_settings_override",
                metadata={
                    "doctype": doctype,
                    "docname": docname
                }
            )
        
        # Importar y ejecutar hook original
        from kreo_whats2.kreo_whats2.overrides.whatsapp_settings_override import WhatsAppSettingsOverride
        return WhatsAppSettingsOverride
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("configuration", e, {
                "hook": "whatsapp_settings_override",
                "doctype": doctype,
                "docname": docname
            })
        raise

def whatsapp_message_override(doctype, docname):
    """Hook de override con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("configuration", "INFO", "WhatsApp Message override aplicado",
                operation="whatsapp_message_override",
                metadata={
                    "doctype": doctype,
                    "docname": docname
                }
            )
        
        # Importar y ejecutar hook original
        from kreo_whats2.kreo_whats2.overrides.whatsapp_message_override import WhatsAppMessageOverride
        return WhatsAppMessageOverride
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("configuration", e, {
                "hook": "whatsapp_message_override",
                "doctype": doctype,
                "docname": docname
            })
        raise

# Función de automatización para eventos críticos
def trigger_critical_event_automation(event_type: str, data: dict):
    """Función para automatizar respuestas a eventos críticos"""
    if not ADVANCED_LOGGING_AVAILABLE:
        return
    
    try:
        # Verificar si es un evento crítico
        if event_type in CRITICAL_EVENTS_CONFIG["security_events"]:
            log_security_hook(event_type, critical=True, **data)
            
            # Enviar alerta automática
            from kreo_whats2.kreo_whats2.utils.alert_manager import trigger_manual_alert
            trigger_manual_alert(
                f"critical_{event_type}",
                f"Evento crítico detectado: {event_type}",
                severity="high",
                metadata=data
            )
            
        # Verificar umbrales de performance
        elif data.get("performance_metric"):
            threshold = CRITICAL_EVENTS_CONFIG["performance_thresholds"].get("slow_operation_ms", 5000)
            if data["performance_metric"] > threshold:
                log_event("performance", "WARNING", f"Operación lenta detectada: {data['performance_metric']}ms",
                    operation="performance_alert",
                    performance_metrics={"duration_ms": data["performance_metric"]},
                    metadata=data
                )
                
        # Verificar métricas de negocio
        elif data.get("business_metric"):
            threshold = CRITICAL_EVENTS_CONFIG["business_metrics"].get("failure_rate_threshold", 0.05)
            if data["business_metric"] > threshold:
                log_event("business", "WARNING", f"Tasa de fallos alta detectada: {data['business_metric']}",
                    operation="business_alert",
                    business_metrics={"failure_rate": data["business_metric"]},
                    metadata=data
                )
                
    except Exception as e:
        log_error("automation", e, {
            "function": "trigger_critical_event_automation",
            "event_type": event_type,
            "data": data
        })

# Función de inicialización de hooks con logging
def initialize_hooks_with_logging():
    """Inicializar hooks con configuración de logging avanzado"""
    if not ADVANCED_LOGGING_AVAILABLE:
        print("Advertencia: Logging avanzado no disponible durante la inicialización de hooks")
        return
    
    try:
        # Configurar logging para módulos específicos
        logger = get_logger("hooks_initialization")
        
        # Registrar inicio de inicialización
        logger.info("Iniciando configuración de hooks con logging avanzado")
        
        # Configurar logging para diferentes componentes
        logging_manager.setup_module_logging("scheduler_hooks")
        logging_manager.setup_module_logging("template_automation_hooks")
        logging_manager.setup_module_logging("sales_invoice_hooks")
        logging_manager.setup_module_logging("lead_hooks")
        
        # Registrar finalización exitosa
        logger.info("Hooks configurados exitosamente con logging avanzado")
        
        # Verificar configuración de eventos críticos
        logger.info(f"Eventos críticos configurados: {len(CRITICAL_EVENTS_CONFIG['security_events'])} tipos de seguridad")
        logger.info(f"Umbrales de performance: {CRITICAL_EVENTS_CONFIG['performance_thresholds']}")
        logger.info(f"Umbrales de negocio: {CRITICAL_EVENTS_CONFIG['business_metrics']}")
        
    except Exception as e:
        log_error("initialization", e, {
            "function": "initialize_hooks_with_logging"
        })
        raise

# === HOOKS DE DOCTYPES DE FRAPPE PARA LOGGING AVANZADO ===

def whatsapp_settings_on_update(doc, method):
    """Hook para registrar cambios en WhatsApp Settings con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "whatsapp_settings_update",
                user=frappe.session.user if frappe.session else "system",
                metadata={
                    "doctype": "WhatsApp Settings",
                    "docname": doc.name,
                    "changed_fields": doc.get_valid_dict().changed if hasattr(doc, 'get_valid_dict') else {}
                }
            )
        
        # Registrar el cambio de configuración
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("configuration", "INFO", "WhatsApp Settings actualizados",
                operation="whatsapp_settings_update",
                business_metrics={"settings_updated": 1},
                metadata={
                    "fields_changed": list(doc.get_valid_dict().changed.keys()) if hasattr(doc, 'get_valid_dict') and doc.get_valid_dict().changed else []
                }
            )
        
        # Verificar si es un cambio crítico
        critical_fields = ["enabled", "api_key", "phone_number", "webhook_url"]
        if ADVANCED_LOGGING_AVAILABLE and hasattr(doc, 'get_valid_dict') and doc.get_valid_dict().changed:
            changed_critical = [field for field in critical_fields if field in doc.get_valid_dict().changed]
            if changed_critical:
                log_security_hook("whatsapp_settings_changed",
                    critical=True,
                    sensitive_operation=True,
                    metadata={
                        "critical_fields_changed": changed_critical,
                        "user": frappe.session.user if frappe.session else "system"
                    }
                )
        
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={"settings_updated": 1}
            )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_settings_hook", e, {
                "hook": "whatsapp_settings_on_update",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })
        raise

def whatsapp_settings_validate(doc, method):
    """Hook para validar WhatsApp Settings con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("validation", "INFO", "Validando WhatsApp Settings",
                operation="whatsapp_settings_validate",
                metadata={
                    "doctype": "WhatsApp Settings",
                    "docname": doc.name,
                    "enabled": doc.enabled if hasattr(doc, 'enabled') else False
                }
            )
        
        # Validaciones específicas con logging
        if hasattr(doc, 'enabled') and doc.enabled:
            required_fields = ["api_key", "phone_number", "webhook_url"]
            missing_fields = [field for field in required_fields if not doc.get(field)]
            
            if missing_fields and ADVANCED_LOGGING_AVAILABLE:
                log_event("validation", "WARNING", f"Campos requeridos faltantes: {missing_fields}",
                    operation="whatsapp_settings_validation",
                    metadata={
                        "missing_fields": missing_fields,
                        "user": frappe.session.user if frappe.session else "system"
                    }
                )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_settings_validation", e, {
                "hook": "whatsapp_settings_validate",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })
        raise

def whatsapp_message_on_submit(doc, method):
    """Hook para registrar envío de mensajes WhatsApp con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            correlation_id = logging_manager.start_operation_context(
                "whatsapp_message_submit",
                user=frappe.session.user if frappe.session else "system",
                metadata={
                    "doctype": "WhatsApp Message",
                    "docname": doc.name,
                    "message_type": doc.message_type if hasattr(doc, 'message_type') else "unknown",
                    "recipient": doc.recipient if hasattr(doc, 'recipient') else "unknown"
                }
            )
        
        # Registrar el mensaje con logging estructurado
        if ADVANCED_LOGGING_AVAILABLE and hasattr(doc, 'message_type'):
            message_data = {
                "message_id": doc.name,
                "template_name": doc.template_name if hasattr(doc, 'template_name') else None,
                "to": doc.recipient if hasattr(doc, 'recipient') else None,
                "type": doc.message_type if hasattr(doc, 'message_type') else "unknown"
            }
            
            log_whatsapp_message(message_data, "submitted",
                metadata={
                    "source": "whatsapp_message_on_submit_hook",
                    "user": frappe.session.user if frappe.session else "system"
                }
            )
        
        if ADVANCED_LOGGING_AVAILABLE:
            logging_manager.end_operation_context(
                correlation_id, "success",
                business_metrics={"messages_submitted": 1}
            )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_message_hook", e, {
                "hook": "whatsapp_message_on_submit",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })
        raise

def whatsapp_message_on_update(doc, method):
    """Hook para registrar actualizaciones de mensajes WhatsApp"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            # Verificar cambios en el estado del mensaje
            if hasattr(doc, 'status') and doc.has_value_changed('status'):
                old_status = doc.get_doc_before_save().status if doc.get_doc_before_save() else None
                new_status = doc.status
                
                log_event("whatsapp_message", "INFO", f"Estado de mensaje cambiado: {old_status} -> {new_status}",
                    operation="whatsapp_message_status_update",
                    metadata={
                        "message_id": doc.name,
                        "old_status": old_status,
                        "new_status": new_status,
                        "user": frappe.session.user if frappe.session else "system"
                    }
                )
                
                # Registrar en el sistema de logging de WhatsApp
                if ADVANCED_LOGGING_AVAILABLE:
                    message_data = {
                        "message_id": doc.name,
                        "template_name": doc.template_name if hasattr(doc, 'template_name') else None,
                        "to": doc.recipient if hasattr(doc, 'recipient') else None,
                        "type": doc.message_type if hasattr(doc, 'message_type') else "unknown"
                    }
                    
                    log_whatsapp_message(message_data, new_status.lower(),
                        metadata={
                            "status_change": f"{old_status}_to_{new_status}",
                            "source": "whatsapp_message_on_update_hook"
                        }
                    )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_message_update_hook", e, {
                "hook": "whatsapp_message_on_update",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })

def whatsapp_template_on_submit(doc, method):
    """Hook para registrar creación de plantillas WhatsApp con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("whatsapp_template", "INFO", "Nueva plantilla WhatsApp creada",
                operation="whatsapp_template_create",
                business_metrics={"templates_created": 1},
                metadata={
                    "template_name": doc.template_name if hasattr(doc, 'template_name') else "unknown",
                    "language": doc.language if hasattr(doc, 'language') else "unknown",
                    "category": doc.category if hasattr(doc, 'category') else "unknown",
                    "user": frappe.session.user if frappe.session else "system"
                }
            )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_template_hook", e, {
                "hook": "whatsapp_template_on_submit",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })

def whatsapp_template_validate(doc, method):
    """Hook para validar plantillas WhatsApp con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_event("validation", "INFO", "Validando plantilla WhatsApp",
                operation="whatsapp_template_validate",
                metadata={
                    "template_name": doc.template_name if hasattr(doc, 'template_name') else "unknown",
                    "validation_stage": "pre_save"
                }
            )
        
        # Validar contenido de la plantilla
        if hasattr(doc, 'template_content') and doc.template_content:
            # Contar variables en la plantilla
            import re
            variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', doc.template_content)
            
            if ADVANCED_LOGGING_AVAILABLE:
                log_event("validation", "INFO", f"Plantilla contiene {len(variables)} variables",
                    operation="template_variable_count",
                    metadata={
                        "template_name": doc.template_name if hasattr(doc, 'template_name') else "unknown",
                        "variables": variables,
                        "content_length": len(doc.template_content) if hasattr(doc, 'template_content') else 0
                    }
                )
        
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("whatsapp_template_validation", e, {
                "hook": "whatsapp_template_validate",
                "docname": doc.name if 'doc' in locals() else "unknown"
            })

# === HOOKS DE EVENTOS DE FRAPPE PARA LOGGING AUTOMÁTICO ===

def on_session_creation(login_manager, **kwargs):
    """Hook para registrar inicio de sesión con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_security_hook("user_login",
                ip_address=frappe.local.request_ip if hasattr(frappe, 'local') and hasattr(frappe.local, 'request_ip') else "unknown",
                user_agent=frappe.local.request.headers.get('User-Agent', 'unknown') if hasattr(frappe, 'local') else "unknown",
                user=login_manager.user,
                metadata={
                    "login_method": "session_creation",
                    "success": True
                }
            )
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("session_hook", e, {
                "hook": "on_session_creation",
                "user": login_manager.user if hasattr(login_manager, 'user') else "unknown"
            })

def on_logout(login_manager, **kwargs):
    """Hook para registrar cierre de sesión con logging avanzado"""
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            log_security_hook("user_logout",
                user=frappe.session.user if frappe.session else "system",
                metadata={
                    "logout_method": "manual",
                    "session_duration": "unknown"
                }
            )
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("session_hook", e, {
                "hook": "on_logout",
                "user": frappe.session.user if frappe.session else "system"
            })

def before_request():
    """Hook para registrar cada request con logging"""
    try:
        if ADVANCED_LOGGING_AVAILABLE and frappe.request:
            log_event("request", "INFO", f"Request: {frappe.request.method} {frappe.request.path}",
                operation="http_request",
                metadata={
                    "method": frappe.request.method,
                    "path": frappe.request.path,
                    "user": frappe.session.user if frappe.session else "system",
                    "ip": frappe.local.request_ip if hasattr(frappe, 'local') and hasattr(frappe.local, 'request_ip') else "unknown"
                }
            )
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            log_error("request_hook", e, {
                "hook": "before_request",
                "path": frappe.request.path if hasattr(frappe, 'request') else "unknown"
            })

# Inicializar hooks al cargar el módulo
if ADVANCED_LOGGING_AVAILABLE:
    initialize_hooks_with_logging()