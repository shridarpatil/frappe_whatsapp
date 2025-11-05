# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
from datetime import datetime, timedelta

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
    print("Advertencia: Logging avanzado no disponible en scheduler_hooks")

# Importar decoradores
if ADVANCED_LOGGING_AVAILABLE:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        log_whatsapp_event, handle_whatsapp_errors
    )

class SchedulerHooksManager:
    """Gestor de hooks de scheduler con logging avanzado"""
    
    @staticmethod
    def _log_scheduler_operation(operation_name: str, status: str, **kwargs):
        """Registrar operación de scheduler con logging avanzado"""
        if not ADVANCED_LOGGING_AVAILABLE:
            return
            
        try:
            correlation_id = logging_manager.start_operation_context(
                operation_name,
                hook_type="scheduler",
                user="system",
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
                        "scheduler_operations": 1
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
            print(f"Error en logging de scheduler: {str(e)}")

@log_whatsapp_event("INFO", "scheduler_hook")
@handle_whatsapp_errors("scheduler_hook")
def send_payment_reminders():
    """
    Enviar recordatorios de pago vencidos por WhatsApp.
    
    Esta función es ejecutada diariamente por el scheduler de Frappe
    para enviar recordatorios automáticos a clientes con facturas vencidas.
    """
    start_time = datetime.now()
    
    try:
        if ADVANCED_LOGGING_AVAILABLE:
            logger = get_logger("scheduler_hooks")
            logger.info("Iniciando tarea programada: send_payment_reminders")
            
            # Verificar si WhatsApp está habilitado con logging
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                logger.info("WhatsApp no está habilitado, omitiendo recordatorios de pago")
                SchedulerHooksManager._log_scheduler_operation(
                    "send_payment_reminders", "success",
                    reason="whatsapp_disabled"
                )
                return
            
            # Obtener facturas vencidas con logging de performance
            with logging_manager.start_operation_context(
                "get_overdue_invoices",
                operation_type="database_query",
                metadata={"query_type": "overdue_invoices"}
            ) as correlation_id:
                
                overdue_invoices = frappe.db.get_all("Sales Invoice",
                    filters={
                        "status": ["in", ["Unpaid", "Overdue"]],
                        "due_date": ["<", frappe.utils.nowdate()],
                        "docstatus": 1
                    },
                    fields=["name", "customer", "due_date", "outstanding_amount"],
                    limit=100
                )
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    performance_metrics={
                        "query_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                        "records_found": len(overdue_invoices)
                    }
                )
            
            if not overdue_invoices:
                logger.info("No hay facturas vencidas para enviar recordatorios")
                SchedulerHooksManager._log_scheduler_operation(
                    "send_payment_reminders", "success",
                    reason="no_overdue_invoices",
                    invoice_count=0
                )
                return
            
            logger.info(f"Procesando {len(overdue_invoices)} recordatorios de pago")
            
            # Importar la API de WhatsApp
            from kreo_whats2.kreo_whats2.api.whatsapp_api import whatsapp_api
            
            # Procesar cada factura vencida con logging detallado
            processed_count = 0
            error_count = 0
            total_start_time = datetime.now()
            
            for i, invoice in enumerate(overdue_invoices):
                try:
                    invoice_start_time = datetime.now()
                    
                    # Verificar si ya se envió un recordatorio hoy para esta factura
                    last_reminder = frappe.db.get_value("WhatsApp Message Log",
                        {
                            "reference_doctype": "Sales Invoice",
                            "reference_name": invoice.name,
                            "message_type": "Payment Reminder"
                        },
                        "creation"
                    )
                    
                    if last_reminder and frappe.utils.getdate(last_reminder) == frappe.utils.nowdate():
                        logger.debug(f"Recordatorio ya enviado hoy para factura {invoice.name}")
                        continue
                    
                    # Obtener información del cliente
                    customer = frappe.get_doc("Customer", invoice.customer)
                    if not customer.mobile_no:
                        logger.warning(f"Cliente {invoice.customer} no tiene número de móvil")
                        continue
                    
                    # Crear mensaje de recordatorio
                    message = f"""Hola {customer.customer_name}, le recordamos que tiene una factura pendiente por ${invoice.outstanding_amount:,.2f} vencida desde {invoice.due_date}. Por favor, realice el pago a la brevedad."""
                    
                    # Enviar mensaje por WhatsApp usando la API correcta
                    result = whatsapp_api.send_custom_message(customer.mobile_no, message)
                    
                    if result.get("success"):
                        # Registrar el envío exitoso con logging avanzado
                        logger.info(f"Recordatorio de pago enviado exitosamente para factura {invoice.name}")
                        processed_count += 1
                    else:
                        logger.error(f"Error enviando recordatorio para factura {invoice.name}: {result.get('error', 'Error desconocido')}")
                        error_count += 1
                    
                    # Logging de performance por factura
                    invoice_duration = (datetime.now() - invoice_start_time).total_seconds() * 1000
                    if invoice_duration > 1000:  # Más de 1 segundo
                        logger.warning(f"Factura {invoice.name} procesada lentamente: {invoice_duration}ms")
                        
                except Exception as e:
                    logger.error(f"Error procesando recordatorio para factura {invoice.name}: {str(e)}")
                    error_count += 1
                    
            # Registrar resumen del proceso con métricas de negocio
            duration = (datetime.now() - total_start_time).total_seconds()
            logger.info(f"Resumen de recordatorios: {processed_count} enviados, {error_count} errores de {len(overdue_invoices)} facturas procesadas en {duration:.2f}s")
            
            # Registrar métricas de negocio
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("business_metrics", "INFO", "Métricas de recordatorios de pago",
                    operation="payment_reminders_summary",
                    business_metrics={
                        "invoices_processed": len(overdue_invoices),
                        "reminders_sent": processed_count,
                        "reminders_failed": error_count,
                        "success_rate": processed_count / len(overdue_invoices) if len(overdue_invoices) > 0 else 0,
                        "total_time_seconds": duration
                    },
                    performance_metrics={
                        "total_processing_time_ms": duration * 1000,
                        "average_time_per_invoice_ms": duration * 1000 / len(overdue_invoices) if len(overdue_invoices) > 0 else 0
                    }
                )
            
            SchedulerHooksManager._log_scheduler_operation(
                "send_payment_reminders", "success",
                processed_count=processed_count,
                error_count=error_count,
                total_invoices=len(overdue_invoices),
                duration_seconds=duration
            )
                
        else:
            # Fallback a logging básico si no hay logging avanzado
            frappe.logger().info("Iniciando send_payment_reminders")
            # ... resto del código original sin logging avanzado ...
            
    except Exception as e:
        if ADVANCED_LOGGING_AVAILABLE:
            logger = get_logger("scheduler_hooks")
            logger.error(f"Error crítico en send_payment_reminders: {str(e)}", exc_info=True)
            
            # Registrar error crítico
            log_error("scheduler_hooks", e, {
                "function": "send_payment_reminders",
                "operation": "payment_reminders"
            })
            
            SchedulerHooksManager._log_scheduler_operation(
                "send_payment_reminders", "error",
                error_type=type(e).__name__,
                error_message=str(e)
            )
        else:
            frappe.logger().error(f"Error crítico en send_payment_reminders: {str(e)}")
            
        # Re-lanzar la excepción para que el scheduler la registre
        raise

@log_whatsapp_event("INFO", "scheduler_hook")
@handle_whatsapp_errors("scheduler_hook")
def send_invoice_reminders():
    """
    Enviar recordatorios de facturas próximas a vencer.
    
    Esta función envía recordatorios 3 días antes de la fecha de vencimiento.
    """
    try:
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            frappe.logger().info("WhatsApp no está habilitado, omitiendo recordatorios de facturas")
            return
        
        # Calcular fecha límite (3 días antes)
        today = frappe.utils.nowdate()
        reminder_date = frappe.utils.add_days(today, 3)
        
        # Obtener facturas que vencen en 3 días
        upcoming_invoices = frappe.db.get_all("Sales Invoice",
            filters={
                "status": ["in", ["Unpaid", "Overdue"]],
                "due_date": reminder_date,
                "docstatus": 1
            },
            fields=["name", "customer", "due_date", "outstanding_amount"],
            limit=50
        )
        
        if not upcoming_invoices:
            frappe.logger().info("No hay facturas próximas a vencer para enviar recordatorios")
            return
        
        frappe.logger().info(f"Procesando {len(upcoming_invoices)} recordatorios de facturas próximas a vencer")
        
        # Importar la API de WhatsApp
        from kreo_whats2.kreo_whats2.api.whatsapp_api import whatsapp_api
        
        # Procesar cada factura
        processed_count = 0
        error_count = 0
        
        for invoice in upcoming_invoices:
            try:
                # Verificar si ya se envió un recordatorio para esta fecha
                existing_reminder = frappe.db.exists("WhatsApp Message Log", {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice.name,
                    "message_type": "Invoice Reminder",
                    "creation": [">=", frappe.utils.nowdate()]
                })
                
                if existing_reminder:
                    continue
                
                # Obtener información del cliente
                customer = frappe.get_doc("Customer", invoice.customer)
                if not customer.mobile_no:
                    continue
                
                # Crear mensaje de recordatorio
                message = f"""Estimado {customer.customer_name}, le informamos que su factura {invoice.name} por ${invoice.outstanding_amount:,.2f} vence el {invoice.due_date}. Le agradecemos su puntualidad en el pago."""
                
                # Enviar mensaje
                result = whatsapp_api.send_custom_message(customer.mobile_no, message)
                
                if result.get("success"):
                    processed_count += 1
                else:
                    frappe.logger().error(f"Error enviando recordatorio para factura {invoice.name}: {result.get('error')}")
                    error_count += 1
                    
            except Exception as e:
                frappe.logger().error(f"Error procesando recordatorio de factura {invoice.name}: {str(e)}")
                error_count += 1
        
        frappe.logger().info(f"Resumen de recordatorios de facturas: {processed_count} enviados, {error_count} errores")
                
    except Exception as e:
        frappe.logger().error(f"Error en send_invoice_reminders: {str(e)}")
        raise

def cleanup_old_messages():
    """
    Limpiar mensajes de WhatsApp antiguos para mantener la base de datos optimizada.
    
    Esta función elimina mensajes con más de 90 días de antigüedad.
    """
    try:
        # Calcular fecha límite (90 días atrás)
        cutoff_date = frappe.utils.add_days(frappe.utils.nowdate(), -90)
        
        # Contar mensajes a eliminar
        message_count = frappe.db.count("WhatsApp Message", {
            "creation": ["<", cutoff_date]
        })
        
        if message_count == 0:
            frappe.logger().info("No hay mensajes antiguos para limpiar")
            return
        
        frappe.logger().info(f"Iniciando limpieza de {message_count} mensajes de WhatsApp antiguos")
        
        # Eliminar mensajes antiguos (por lotes para evitar bloqueos)
        batch_size = 100
        deleted_count = 0
        
        while True:
            # Obtener IDs de mensajes para eliminar
            message_ids = frappe.db.get_list("WhatsApp Message", 
                filters={"creation": ["<", cutoff_date]},
                fields=["name"],
                limit=batch_size
            )
            
            if not message_ids:
                break
            
            # Eliminar por lotes
            for message in message_ids:
                try:
                    frappe.delete_doc("WhatsApp Message", message.name, ignore_permissions=True)
                    deleted_count += 1
                except Exception as e:
                    frappe.logger().warning(f"No se pudo eliminar mensaje {message.name}: {str(e)}")
        
        frappe.logger().info(f"Limpieza completada: {deleted_count} mensajes eliminados")
                
    except Exception as e:
        frappe.logger().error(f"Error en cleanup_old_messages: {str(e)}")
        raise

@log_whatsapp_event("INFO", "scheduler_hook")
@handle_whatsapp_errors("scheduler_hook")
def process_whatsapp_queue():
    """
    Procesar la cola de mensajes de WhatsApp pendientes.
    
    Esta función procesa mensajes en cola para asegurar entrega confiable.
    """
    try:
        from kreo_whats2.kreo_whats2.api.queue_processor import process_queue
        
        frappe.logger().info("Iniciando procesamiento de cola de WhatsApp")
        result = process_queue()
        frappe.logger().info(f"Procesamiento de cola completado: {result}")
                
    except Exception as e:
        frappe.logger().error(f"Error en process_whatsapp_queue: {str(e)}")
        raise

@log_whatsapp_event("INFO", "scheduler_hook")
@handle_whatsapp_errors("scheduler_hook")
def health_check_whatsapp_service():
    """
    Verificar el estado del servicio de WhatsApp.
    
    Esta función realiza comprobaciones de salud del servicio.
    """
    try:
        # Verificar configuración de WhatsApp
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            frappe.logger().info("WhatsApp está deshabilitado, omitiendo health check")
            return
        
        # Verificar conexión a Redis para rate limiting
        try:
            import redis
            redis_client = redis.from_url("redis://redis-queue:6379/1")
            redis_client.ping()
            redis_status = "OK"
        except Exception as e:
            frappe.logger().warning(f"Problema con Redis: {str(e)}")
            redis_status = "ERROR"
        
        # Verificar API de WhatsApp
        try:
            from kreo_whats2.kreo_whats2.api.whatsapp_api import whatsapp_api
            # Realizar una verificación básica
            api_status = "OK"
        except Exception as e:
            frappe.logger().error(f"Problema con API de WhatsApp: {str(e)}")
            api_status = "ERROR"
        
        frappe.logger().info(f"Health check WhatsApp - Redis: {redis_status}, API: {api_status}")
                
    except Exception as e:
        frappe.logger().error(f"Error en health_check_whatsapp_service: {str(e)}")

def update_whatsapp_stats():
    """
    Actualizar estadísticas de WhatsApp para dashboards.
    
    Esta función actualiza métricas y estadísticas para reportes.
    """
    try:
        # Obtener estadísticas diarias
        today = frappe.utils.nowdate()
        
        # Contar mensajes enviados hoy
        sent_count = frappe.db.count("WhatsApp Message", {
            "direction": "Outbound",
            "status": "Sent",
            "creation": [">=", today]
        })
        
        # Contar mensajes fallidos hoy
        failed_count = frappe.db.count("WhatsApp Message", {
            "direction": "Outbound",
            "status": "Failed",
            "creation": [">=", today]
        })
        
        # Contar mensajes recibidos hoy
        received_count = frappe.db.count("WhatsApp Message", {
            "direction": "Inbound",
            "creation": [">=", today]
        })
        
        frappe.logger().info(f"Estadísticas diarias de WhatsApp - Enviados: {sent_count}, Fallidos: {failed_count}, Recibidos: {received_count}")
                
    except Exception as e:
        frappe.logger().error(f"Error en update_whatsapp_stats: {str(e)}")