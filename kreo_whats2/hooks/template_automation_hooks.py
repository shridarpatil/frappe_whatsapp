#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Hooks para automatización de plantillas de WhatsApp
Implementa disparadores para envío automático de plantillas basado en eventos de documentos
"""

import frappe
from frappe import _
import json
from datetime import datetime

# Importar logging avanzado completo
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error, log_performance,
        log_whatsapp_event, handle_whatsapp_errors, log_security_event,
        get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible en template_automation_hooks")

from kreo_whats2.kreo_whats2.api.template_renderer import template_renderer
from kreo_whats2.kreo_whats2.api.queue_processor import queue_processor

# Importar decoradores
if ADVANCED_LOGGING_AVAILABLE:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        log_whatsapp_event, handle_whatsapp_errors
    )

logger = get_logger("template_automation_hooks") if ADVANCED_LOGGING_AVAILABLE else frappe.logger()

class TemplateAutomationHooks:
    """Gestión de automatización con plantillas para WhatsApp con logging avanzado"""
    
    @staticmethod
    def _log_template_operation(operation_name: str, status: str, **kwargs):
        """Registrar operación de template automation con logging avanzado"""
        if not ADVANCED_LOGGING_AVAILABLE:
            return
            
        try:
            correlation_id = logging_manager.start_operation_context(
                operation_name,
                hook_type="template_automation",
                user=frappe.session.user if frappe.session else "system",
                metadata={
                    "operation": operation_name,
                    "status": status,
                    "timestamp": datetime.now().isoformat(),
                    **kwargs
                }
            )
            
            if status == "success":
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "template_operations": 1
                    }
                )
            else:
                logging_manager.end_operation_context(
                    correlation_id, "error",
                    error_details={
                        "error_type": kwargs.get("error_type", "unknown"),
                        "error_message": kwargs.get("error_message", "Unknown error")
                    }
                )
                
        except Exception as e:
            print(f"Error en logging de template automation: {str(e)}")
    
    @staticmethod
    @log_whatsapp_event("INFO", "template_automation")
    @handle_whatsapp_errors("template_automation")
    def send_invoice_template(doc, method):
        """Enviar plantilla de factura emitida con logging avanzado"""
        start_time = datetime.now()
        
        try:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.info("Iniciando automatización de plantilla de factura", extra={
                    'document_name': doc.name,
                    'document_type': doc.doctype,
                    'customer': doc.customer_name,
                    'amount': doc.grand_total,
                    'currency': doc.currency,
                    'method': method
                })
                
                # Registrar inicio de operación
                correlation_id = logging_manager.start_operation_context(
                    "send_invoice_template",
                    document_type=doc.doctype,
                    document_name=doc.name,
                    customer=doc.customer_name,
                    amount=doc.grand_total,
                    metadata={
                        "operation": "template_automation",
                        "trigger_method": method,
                        "has_contact_mobile": bool(doc.contact_mobile)
                    }
                )
                
                # Verificar si WhatsApp está habilitado con logging de seguridad
                whatsapp_settings = frappe.get_single("WhatsApp Settings")
                
                if not whatsapp_settings.enabled:
                    logger.info("WhatsApp no está habilitado, omitiendo automatización")
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        metadata={"reason": "whatsapp_disabled"}
                    )
                    return
                
                # Verificar si el cliente tiene teléfono
                if not doc.contact_mobile:
                    logger.info("Cliente no tiene número de teléfono, omitiendo automatización")
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        metadata={"reason": "no_contact_mobile"}
                    )
                    return
                
                # Determinar si usar sistema de plantillas o legacy
                use_templates = getattr(whatsapp_settings, 'use_template_system', True)
                
                if use_templates:
                    logger.info("Usando sistema de plantillas avanzado")
                    result = TemplateAutomationHooks._send_template_invoice(doc, correlation_id)
                else:
                    logger.info("Usando sistema legacy")
                    result = TemplateAutomationHooks._send_legacy_invoice(doc, correlation_id)
                
                # Registrar métricas de negocio
                duration = (datetime.now() - start_time).total_seconds()
                logging_manager.log_event("business_metrics", "INFO", "Métricas de automatización de factura",
                    operation="invoice_template_sent",
                    business_metrics={
                        "template_sent": 1,
                        "template_type": "invoice",
                        "amount": doc.grand_total,
                        "currency": doc.currency
                    },
                    performance_metrics={
                        "processing_time_ms": duration * 1000
                    },
                    metadata={
                        "document_name": doc.name,
                        "customer": doc.customer_name,
                        "use_templates": use_templates
                    }
                )
                
                return result
                
            else:
                # Fallback a logging básico
                logger.info(f"Iniciando automatización de factura {doc.name}")
                whatsapp_settings = frappe.get_single("WhatsApp Settings")
                
                if not whatsapp_settings.enabled:
                    logger.info("WhatsApp no está habilitado")
                    return
                
                if not doc.contact_mobile:
                    logger.info("Cliente no tiene número de teléfono")
                    return
                
                use_templates = getattr(whatsapp_settings, 'use_template_system', True)
                if use_templates:
                    return TemplateAutomationHooks._send_template_invoice(doc)
                else:
                    return TemplateAutomationHooks._send_legacy_invoice(doc)
                
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.error(f"Error en automatización de factura: {str(e)}", exc_info=True)
                
                # Registrar error con contexto completo
                log_error("template_automation", e, {
                    "function": "send_invoice_template",
                    "document_name": doc.name if 'doc' in locals() else "unknown",
                    "document_type": doc.doctype if 'doc' in locals() else "unknown",
                    "method": method if 'method' in locals() else "unknown"
                })
                
                # Registrar operación fallida
                if 'correlation_id' in locals():
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
            else:
                logger.error(f"Error en automatización de factura: {str(e)}")
                frappe.log_error(f"Error en automatización de factura: {str(e)}")
            raise
    
    @staticmethod
    def _send_template_invoice(doc, correlation_id=None):
        """Enviar factura usando sistema de plantillas con logging avanzado"""
        start_time = datetime.now()
        
        try:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.info("Iniciando envío de plantilla de factura", extra={
                    'document_name': doc.name,
                    'document_type': doc.doctype,
                    'customer': doc.customer_name,
                    'amount': doc.grand_total,
                    'currency': doc.currency,
                    'correlation_id': correlation_id
                })
                
                # Registrar operación de envío de plantilla
                if correlation_id:
                    logging_manager.log_event("template_operation", "INFO", "Iniciando envío de plantilla de factura",
                        operation="template_invoice_send",
                        template_type="factura_emitida",
                        business_metrics={
                            "template_type": "invoice",
                            "amount": doc.grand_total,
                            "currency": doc.currency
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "template_name": "factura_emitida"
                        }
                    )
                
                # Preparar datos para la plantilla con logging
                invoice_data = {
                    "invoice_number": doc.name,
                    "amount": f"{doc.grand_total:,.2f}",
                    "currency": doc.currency,
                    "due_date": doc.due_date.strftime('%d/%m/%Y') if doc.due_date else '',
                    "issue_date": doc.posting_date.strftime('%d/%m/%Y') if doc.posting_date else '',
                    "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
                    "payment_url": f"https://kreo.localhost/app/pay/{doc.name}",
                    "customer_name": doc.customer_name,
                    "customer_email": doc.contact_email,
                    "company_name": getattr(frappe.get_single("WhatsApp Settings"), 'company_name', 'KREO'),
                    "support_email": getattr(frappe.get_single("WhatsApp Settings"), 'support_email', 'soporte@kreo.com.co'),
                    "custom_message": "Gracias por su compra. Estamos a su disposición para cualquier consulta."
                }
                
                # Renderizar plantilla con logging
                logger.info("Renderizando plantilla factura_emitida", extra={
                    'template_name': 'factura_emitida',
                    'customer': doc.customer_name
                })
                
                rendered_content = template_renderer.render_template(
                    "factura_emitida",
                    invoice_data
                )
                
                # Preparar mensaje para Redis Queue con logging
                message_data = {
                    "message_id": f"invoice_{doc.name}_{int(datetime.now().timestamp())}",
                    "recipient_phone": doc.contact_mobile,
                    "content": rendered_content,
                    "template_name": "factura_emitida",
                    "template_data": json.dumps(invoice_data),
                    "priority": "high",
                    "max_retries": 3,
                    "retry_interval": 300
                }
                
                # Enviar a la cola con logging
                logger.info("Enviando mensaje a Redis Queue", extra={
                    'message_id': message_data["message_id"],
                    'recipient_phone': doc.contact_mobile,
                    'template_name': 'factura_emitida'
                })
                
                queue_result = queue_processor.redis_client.lpush(
                    getattr(frappe.get_single("WhatsApp Settings"), 'redis_queue_name', 'kreo_whatsapp_queue'),
                    json.dumps(message_data)
                )
                
                if queue_result:
                    # Registrar éxito con logging avanzado
                    doc.db_set("whatsapp_message_sent", 1)
                    doc.db_set("whatsapp_message_id", message_data["message_id"])
                    doc.db_set("whatsapp_sent_timestamp", datetime.now())
                    
                    # Registrar métricas de performance
                    duration = (datetime.now() - start_time).total_seconds()
                    logging_manager.log_event("template_operation", "SUCCESS", "Plantilla de factura enviada exitosamente",
                        operation="template_invoice_sent",
                        business_metrics={
                            "template_sent": 1,
                            "template_type": "invoice",
                            "amount": doc.grand_total,
                            "currency": doc.currency
                        },
                        performance_metrics={
                            "processing_time_ms": duration * 1000,
                            "queue_response_time": getattr(queue_processor, '_last_response_time', 0)
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "message_id": message_data["message_id"],
                            "correlation_id": correlation_id
                        }
                    )
                    
                    frappe.msgprint(
                        _("✅ Mensaje WhatsApp en cola para factura {0}").format(doc.name),
                        alert=True
                    )
                    
                    return {"success": True, "message_id": message_data["message_id"]}
                else:
                    # Registrar error de cola
                    logging_manager.log_event("template_operation", "ERROR", "Error al enviar a Redis Queue",
                        operation="template_invoice_queue_error",
                        error_details={
                            "error_type": "queue_error",
                            "error_message": "Failed to enqueue message"
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "message_id": message_data["message_id"]
                        }
                    )
                    return {"success": False, "error": "Failed to enqueue message"}
                
            else:
                # Fallback a implementación básica
                invoice_data = {
                    "invoice_number": doc.name,
                    "amount": f"{doc.grand_total:,.2f}",
                    "currency": doc.currency,
                    "due_date": doc.due_date.strftime('%d/%m/%Y') if doc.due_date else '',
                    "issue_date": doc.posting_date.strftime('%d/%m/%Y') if doc.posting_date else '',
                    "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
                    "payment_url": f"https://kreo.localhost/app/pay/{doc.name}",
                    "customer_name": doc.customer_name,
                    "customer_email": doc.contact_email,
                    "company_name": getattr(frappe.get_single("WhatsApp Settings"), 'company_name', 'KREO'),
                    "support_email": getattr(frappe.get_single("WhatsApp Settings"), 'support_email', 'soporte@kreo.com.co'),
                    "custom_message": "Gracias por su compra. Estamos a su disposición para cualquier consulta."
                }
                
                rendered_content = template_renderer.render_template(
                    "factura_emitida",
                    invoice_data
                )
                
                message_data = {
                    "message_id": f"invoice_{doc.name}_{int(datetime.now().timestamp())}",
                    "recipient_phone": doc.contact_mobile,
                    "content": rendered_content,
                    "template_name": "factura_emitida",
                    "template_data": json.dumps(invoice_data),
                    "priority": "high",
                    "max_retries": 3,
                    "retry_interval": 300
                }
                
                queue_result = queue_processor.redis_client.lpush(
                    getattr(frappe.get_single("WhatsApp Settings"), 'redis_queue_name', 'kreo_whatsapp_queue'),
                    json.dumps(message_data)
                )
                
                if queue_result:
                    doc.db_set("whatsapp_message_sent", 1)
                    doc.db_set("whatsapp_message_id", message_data["message_id"])
                    doc.db_set("whatsapp_sent_timestamp", datetime.now())
                    
                    frappe.msgprint(
                        _("✅ Mensaje WhatsApp en cola para factura {0}").format(doc.name),
                        alert=True
                    )
                    
                    return {"success": True, "message_id": message_data["message_id"]}
                else:
                    return {"success": False, "error": "Failed to enqueue message"}
                
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.error(f"Error en envío de plantilla de factura: {str(e)}", exc_info=True)
                
                # Registrar error con contexto completo
                log_error("template_automation", e, {
                    "function": "_send_template_invoice",
                    "document_name": doc.name,
                    "document_type": doc.doctype,
                    "correlation_id": correlation_id,
                    "customer": doc.customer_name
                })
                
                # Registrar operación fallida
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        },
                        business_metrics={
                            "failed_template_operations": 1
                        }
                    )
                
                # Registrar evento de seguridad si es un error crítico
                if "queue" in str(e).lower() or "redis" in str(e).lower():
                    log_security_event("HIGH", "template_automation", "Error crítico en cola Redis para plantilla de factura",
                        severity="HIGH",
                        threat_type="infrastructure_failure",
                        indicators={
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "document_name": doc.name,
                            "customer": doc.customer_name
                        }
                    )
            else:
                logger.error(f"Error en envío de plantilla de factura: {str(e)}")
                frappe.log_error(f"Error enviando plantilla de factura: {str(e)}")
            
            raise
    
    @staticmethod
    def _send_legacy_invoice(doc, correlation_id=None):
        """Enviar factura usando sistema legacy con logging avanzado"""
        start_time = datetime.now()
        
        try:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.info("Iniciando envío legacy de factura", extra={
                    'document_name': doc.name,
                    'document_type': doc.doctype,
                    'customer': doc.customer_name,
                    'amount': doc.grand_total,
                    'currency': doc.currency,
                    'correlation_id': correlation_id
                })
                
                # Registrar operación legacy
                if correlation_id:
                    logging_manager.log_event("legacy_operation", "INFO", "Iniciando envío legacy de factura",
                        operation="legacy_invoice_send",
                        business_metrics={
                            "legacy_operations": 1,
                            "amount": doc.grand_total,
                            "currency": doc.currency
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "operation_type": "legacy"
                        }
                    )
                
                from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
                
                invoice_data = {
                    "invoice_number": doc.name,
                    "amount": doc.grand_total,
                    "currency": doc.currency,
                    "due_date": doc.due_date.strftime('%d/%m/%Y') if doc.due_date else '',
                    "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
                    "customer_name": doc.customer_name,
                    "customer_email": doc.contact_email
                }
                
                # Enviar mensaje con logging
                logger.info("Enviando mensaje legacy a WhatsApp", extra={
                    'document_name': doc.name,
                    'customer': doc.customer_name,
                    'template_name': 'factura_emitida'
                })
                
                result = WhatsAppMessage.send_message(
                    recipient_phone=doc.contact_mobile,
                    template_name="factura_emitida",
                    template_data=invoice_data
                )
                
                if result.get("success"):
                    # Registrar éxito con logging avanzado
                    doc.db_set("whatsapp_message_sent", 1)
                    doc.db_set("whatsapp_message_id", result.get("message_id"))
                    doc.db_set("whatsapp_sent_timestamp", datetime.now())
                    
                    # Registrar métricas de performance
                    duration = (datetime.now() - start_time).total_seconds()
                    logging_manager.log_event("legacy_operation", "SUCCESS", "Envío legacy de factura exitoso",
                        operation="legacy_invoice_sent",
                        business_metrics={
                            "legacy_sent": 1,
                            "amount": doc.grand_total,
                            "currency": doc.currency
                        },
                        performance_metrics={
                            "processing_time_ms": duration * 1000
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "message_id": result.get("message_id"),
                            "correlation_id": correlation_id
                        }
                    )
                    
                    return {"success": True, "message_id": result.get("message_id")}
                else:
                    # Registrar error en envío legacy
                    logging_manager.log_event("legacy_operation", "ERROR", "Error en envío legacy de factura",
                        operation="legacy_invoice_error",
                        error_details={
                            "error_type": "send_error",
                            "error_message": result.get("error", "Unknown error")
                        },
                        metadata={
                            "document_name": doc.name,
                            "customer": doc.customer_name,
                            "result": result
                        }
                    )
                    return {"success": False, "error": result.get("error", "Unknown error")}
                
            else:
                # Fallback a implementación básica
                from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
                
                invoice_data = {
                    "invoice_number": doc.name,
                    "amount": doc.grand_total,
                    "currency": doc.currency,
                    "due_date": doc.due_date.strftime('%d/%m/%Y') if doc.due_date else '',
                    "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
                    "customer_name": doc.customer_name,
                    "customer_email": doc.contact_email
                }
                
                result = WhatsAppMessage.send_message(
                    recipient_phone=doc.contact_mobile,
                    template_name="factura_emitida",
                    template_data=invoice_data
                )
                
                if result.get("success"):
                    doc.db_set("whatsapp_message_sent", 1)
                    doc.db_set("whatsapp_message_id", result.get("message_id"))
                    doc.db_set("whatsapp_sent_timestamp", datetime.now())
                    
                    return {"success": True, "message_id": result.get("message_id")}
                else:
                    return {"success": False, "error": result.get("error", "Unknown error")}
                
        except Exception as e:
            if ADVANCED_LOGGING_AVAILABLE:
                logger.error(f"Error en sistema legacy de factura: {str(e)}", exc_info=True)
                
                # Registrar error con contexto completo
                log_error("template_automation", e, {
                    "function": "_send_legacy_invoice",
                    "document_name": doc.name,
                    "document_type": doc.doctype,
                    "correlation_id": correlation_id,
                    "customer": doc.customer_name
                })
                
                # Registrar operación fallida
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        },
                        business_metrics={
                            "failed_legacy_operations": 1
                        }
                    )
                
                # Registrar evento de seguridad si es un error crítico
                if "whatsapp" in str(e).lower() or "api" in str(e).lower():
                    log_security_event("MEDIUM", "template_automation", "Error en API de WhatsApp para envío legacy",
                        severity="MEDIUM",
                        threat_type="api_failure",
                        indicators={
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "document_name": doc.name,
                            "customer": doc.customer_name
                        }
                    )
            else:
                logger.error(f"Error en sistema legacy de factura: {str(e)}")
                frappe.log_error(f"Error en sistema legacy de factura: {str(e)}")
            
            return {"success": False, "error": str(e)}
    
    @staticmethod
    @log_whatsapp_event("INFO", "template_automation")
    @handle_whatsapp_errors("template_automation")
    def send_payment_reminder_template(doc, method):
        """Enviar plantilla de recordatorio de pago"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                return
            
            if not doc.contact_mobile:
                return
            
            # Verificar si es una factura vencida
            if not doc.due_date or doc.due_date > datetime.now().date():
                return
            
            use_templates = getattr(whatsapp_settings, 'use_template_system', True)
            
            if use_templates:
                TemplateAutomationHooks._send_template_payment_reminder(doc)
            else:
                TemplateAutomationHooks._send_legacy_payment_reminder(doc)
                
        except Exception as e:
            frappe.log_error(f"Error en recordatorio de pago: {str(e)}")
    
    @staticmethod
    def _send_template_payment_reminder(doc):
        """Enviar recordatorio usando plantilla"""
        try:
            # Calcular días de retraso
            days_overdue = (datetime.now().date() - doc.due_date).days
            
            reminder_data = {
                "invoice_number": doc.name,
                "amount": f"{doc.grand_total:,.2f}",
                "currency": doc.currency,
                "due_date": doc.due_date.strftime('%d/%m/%Y'),
                "days_overdue": days_overdue,
                "payment_url": f"https://kreo.localhost/app/pay/{doc.name}",
                "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
                "reschedule_url": f"https://kreo.localhost/app/reschedule/{doc.name}",
                "customer_name": doc.customer_name,
                "support_email": getattr(frappe.get_single("WhatsApp Settings"), 'support_email', 'soporte@kreo.com.co'),
                "penalty_info": f"Se aplicará un recargo del 2% por día de retraso después del día {days_overdue + 5}" if days_overdue > 5 else None,
                "custom_message": "Le recordamos que su factura está vencida. Realice el pago para evitar cargos adicionales."
            }
            
            rendered_content = template_renderer.render_template(
                "recordatorio_pago",
                reminder_data
            )
            
            message_data = {
                "message_id": f"reminder_{doc.name}_{int(datetime.now().timestamp())}",
                "recipient_phone": doc.contact_mobile,
                "content": rendered_content,
                "template_name": "recordatorio_pago",
                "template_data": json.dumps(reminder_data),
                "priority": "high",
                "max_retries": 3,
                "retry_interval": 600  # 10 minutos para recordatorios
            }
            
            queue_result = queue_processor.redis_client.lpush(
                getattr(frappe.get_single("WhatsApp Settings"), 'redis_queue_name', 'kreo_whatsapp_queue'),
                json.dumps(message_data)
            )
            
            if queue_result:
                frappe.msgprint(
                    _("✅ Recordatorio de pago en cola para factura {0}").format(doc.name),
                    alert=True
                )
                
        except Exception as e:
            frappe.log_error(f"Error enviando recordatorio de pago: {str(e)}")
    
    @staticmethod
    def _send_legacy_payment_reminder(doc):
        """Enviar recordatorio usando sistema legacy"""
        try:
            from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
            
            reminder_data = {
                "invoice_number": doc.name,
                "amount": doc.grand_total,
                "currency": doc.currency,
                "due_date": doc.due_date.strftime('%d/%m/%Y'),
                "customer_name": doc.customer_name
            }
            
            result = WhatsAppMessage.send_message(
                recipient_phone=doc.contact_mobile,
                template_name="recordatorio_pago",
                template_data=reminder_data
            )
            
            if result.get("success"):
                frappe.msgprint(
                    _("✅ Recordatorio de pago enviado para factura {0}").format(doc.name),
                    alert=True
                )
                
        except Exception as e:
            frappe.log_error(f"Error en recordatorio legacy: {str(e)}")
    
    @staticmethod
    @log_whatsapp_event("INFO", "template_automation")
    @handle_whatsapp_errors("template_automation")
    def send_lead_welcome_template(doc, method):
        """Enviar plantilla de bienvenida a nuevos leads"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                return
            
            if not doc.mobile_no:
                return
            
            use_templates = getattr(whatsapp_settings, 'use_template_system', True)
            
            if use_templates:
                TemplateAutomationHooks._send_template_lead_welcome(doc)
            else:
                TemplateAutomationHooks._send_legacy_lead_welcome(doc)
                
        except Exception as e:
            frappe.log_error(f"Error en bienvenida de lead: {str(e)}")
    
    @staticmethod
    def _send_template_lead_welcome(doc):
        """Enviar bienvenida usando plantilla"""
        try:
            welcome_data = {
                "lead_name": doc.lead_name or doc.company_name or "Estimado cliente",
                "company_name": getattr(frappe.get_single("WhatsApp Settings"), 'company_name', 'KREO'),
                "support_email": getattr(frappe.get_single("WhatsApp Settings"), 'support_email', 'soporte@kreo.com.co'),
                "support_phone": getattr(frappe.get_single("WhatsApp Settings"), 'support_phone', '+57 123 456 7890'),
                "catalog_url": "https://kreo.com.co/catalogo",
                "contact_url": "https://kreo.com.co/contacto",
                "whatsapp_url": "https://wa.me/571234567890",
                "special_offer": "¡Bienvenido! 10% de descuento en su primera compra",
                "testimonials": [
                    {"text": "Excelente servicio y productos de alta calidad", "author": "Cliente Satisfecho"},
                    {"text": "Entrega rápida y atención personalizada", "author": "Usuario Recurrente"}
                ],
                "custom_message": "Estamos encantados de que haya mostrado interés en nuestros servicios."
            }
            
            rendered_content = template_renderer.render_template(
                "bienvenida_lead",
                welcome_data
            )
            
            message_data = {
                "message_id": f"welcome_{doc.name}_{int(datetime.now().timestamp())}",
                "recipient_phone": doc.mobile_no,
                "content": rendered_content,
                "template_name": "bienvenida_lead",
                "template_data": json.dumps(welcome_data),
                "priority": "normal",
                "max_retries": 2,
                "retry_interval": 900  # 15 minutos
            }
            
            queue_result = queue_processor.redis_client.lpush(
                getattr(frappe.get_single("WhatsApp Settings"), 'redis_queue_name', 'kreo_whatsapp_queue'),
                json.dumps(message_data)
            )
            
            if queue_result:
                doc.db_set("whatsapp_welcome_sent", 1)
                doc.db_set("whatsapp_welcome_id", message_data["message_id"])
                doc.db_set("whatsapp_welcome_timestamp", datetime.now())
                
                frappe.msgprint(
                    _("✅ Mensaje de bienvenida en cola para lead {0}").format(doc.lead_name or doc.company_name),
                    alert=True
                )
                
        except Exception as e:
            frappe.log_error(f"Error enviando bienvenida de lead: {str(e)}")
    
    @staticmethod
    def _send_legacy_lead_welcome(doc):
        """Enviar bienvenida usando sistema legacy"""
        try:
            from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
            
            welcome_data = {
                "lead_name": doc.lead_name or doc.company_name or "Estimado cliente",
                "company_name": getattr(frappe.get_single("WhatsApp Settings"), 'company_name', 'KREO')
            }
            
            result = WhatsAppMessage.send_message(
                recipient_phone=doc.mobile_no,
                template_name="bienvenida_lead",
                template_data=welcome_data
            )
            
            if result.get("success"):
                doc.db_set("whatsapp_welcome_sent", 1)
                doc.db_set("whatsapp_welcome_id", result.get("message_id"))
                doc.db_set("whatsapp_welcome_timestamp", datetime.now())
                
        except Exception as e:
            frappe.log_error(f"Error en bienvenida legacy: {str(e)}")

# Funciones de compatibilidad para los hooks existentes
def sales_invoice_on_submit(doc, method):
    """Wrapper para compatibilidad con hooks existentes"""
    TemplateAutomationHooks.send_invoice_template(doc, method)

def sales_invoice_on_cancel(doc, method):
    """Wrapper para cancelación de factura"""
    # Usar sistema legacy para cancelaciones por ahora
    try:
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        if not doc.contact_mobile:
            return
        
        from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
        
        cancel_data = {
            "invoice_number": doc.name,
            "customer_name": doc.customer_name,
            "cancel_reason": doc.get_formatted("reason_for_cancellation") or "No especificada",
            "cancelled_by": frappe.session.user.full_name
        }
        
        message_content = f"""📄 *Factura Cancelada*

Factura: {doc.name}
Cliente: {doc.customer_name}
Motivo: {cancel_data['cancel_reason']}
Cancelada por: {cancel_data['cancelled_by']}

Para más información, contacte a soporte@kreo.com.co"""
        
        result = WhatsAppMessage.send_message(
            recipient_phone=doc.contact_mobile,
            message_content=message_content
        )
        
        if result.get("success"):
            frappe.msgprint(
                _("✅ Mensaje WhatsApp enviado para factura cancelada {0}").format(doc.name),
                alert=True
            )
            
    except Exception as e:
        frappe.log_error(f"Error en cancelación de factura: {str(e)}")

def lead_on_submit(doc, method):
    """Wrapper para compatibilidad con leads"""
    TemplateAutomationHooks.send_lead_welcome_template(doc, method)

def payment_reminder_scheduler():
    """Tarea programada para enviar recordatorios de pago"""
    try:
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        # Obtener facturas vencidas que no han sido notificadas hoy
        today = datetime.now().date()
        
        invoices = frappe.get_all("Sales Invoice", filters={
            "docstatus": 1,
            "status": ["!=", "Paid"],
            "due_date": ["<", today],
            "whatsapp_reminder_sent": 0
        }, fields=["name"])
        
        for invoice in invoices:
            try:
                doc = frappe.get_doc("Sales Invoice", invoice.name)
                TemplateAutomationHooks.send_payment_reminder_template(doc, "scheduler")
                
                # Marcar como notificada para evitar duplicados
                doc.db_set("whatsapp_reminder_sent", 1)
                
            except Exception as e:
                frappe.log_error(f"Error en recordatorio programado para {invoice.name}: {str(e)}")
                
    except Exception as e:
        frappe.log_error(f"Error en tarea programada de recordatorios: {str(e)}")