# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
from datetime import datetime

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import log_whatsapp_event, handle_whatsapp_errors
    ADVANCED_LOGGING_AVAILABLE = True
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False

def sales_invoice_on_submit(doc, method=None):
    """
    Hook de submit de Sales Invoice.
    NOTA: El envío de WhatsApp NO se hace aquí, sino desde dian_controller
    cuando la factura sea aprobada por DIAN.
    """
    # Si hay lógica de validación, mantenerla aquí
    # PERO remover cualquier llamada a envío de WhatsApp
    pass  # O lógica que NO incluya envío de WhatsApp

@log_whatsapp_event("INFO", "sales_invoice_hook")
@handle_whatsapp_errors("sales_invoice_hook")
def sales_invoice_on_cancel(doc, method):
    """Enviar mensaje WhatsApp cuando se cancela una factura"""
    try:
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        # Verificar si el cliente tiene teléfono
        if not doc.contact_mobile:
            return
        
        # Preparar datos del mensaje
        cancel_data = {
            "invoice_number": doc.name,
            "customer_name": doc.customer_name,
            "cancel_reason": doc.get_formatted("reason_for_cancellation") or "No especificada",
            "cancelled_by": frappe.session.user.full_name if frappe.session.user else "Sistema"
        }
        
        # Enviar mensaje personalizado
        from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
        
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
            frappe.msgprint(_("✅ Mensaje WhatsApp enviado para factura cancelada {0}").format(doc.name), alert=True)
        else:
            frappe.msgprint(_("❌ Error enviando mensaje WhatsApp para factura cancelada {0}: {1}").format(doc.name, result.get("error")), alert=True)
            
    except Exception as e:
        frappe.log_error(f"Error en hook de cancelación de Sales Invoice: {str(e)}")


def send_invoice_whatsapp(invoice_name):
    """
    Envía mensaje de WhatsApp para una factura.
    Esta función debe ser llamada SOLO después de aprobación DIAN.
    
    Args:
        invoice_name (str): Nombre del documento de factura
    """
    try:
        # Cargar el documento de la factura
        doc = frappe.get_doc('Sales Invoice', invoice_name)
        
        # Verificar que la factura esté aprobada por DIAN
        if not doc.dian_status or doc.dian_status != 'Approved':
            frappe.logger().warning(f"Factura {doc.name} no está aprobada por DIAN (estado: {doc.dian_status}), no se enviará WhatsApp")
            return
        
        # Verificar que no se haya enviado ya (idempotencia)
        existing_message = frappe.db.exists('WhatsApp Message', {
            'reference_doctype': 'Sales Invoice',
            'reference_name': doc.name,
            'status': ['in', ['Sent', 'Delivered', 'Read']]
        })
        
        if existing_message:
            frappe.logger().info(f"WhatsApp ya enviado para factura {doc.name}")
            return
        
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            frappe.logger().info(f"WhatsApp deshabilitado para factura {doc.name}")
            return
        
        # Verificar si el cliente tiene teléfono
        if not doc.contact_mobile:
            frappe.logger().info(f"Cliente sin teléfono móvil para factura {doc.name}")
            return
        
        # Obtener información de la factura
        invoice_data = {
            "invoice_number": doc.name,
            "amount": doc.grand_total,
            "currency": doc.currency,
            "due_date": doc.due_date.strftime('%d/%m/%Y') if doc.due_date else '',
            "invoice_url": f"https://kreo.localhost/app/invoice/{doc.name}",
            "customer_name": doc.customer_name,
            "customer_email": doc.contact_email
        }
        
        # Enviar mensaje usando plantilla
        from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
        
        result = WhatsAppMessage.send_message(
            recipient_phone=doc.contact_mobile,
            template_name="factura_emitida",
            template_data=invoice_data
        )
        
        if result.get("success"):
            # Registrar referencia en la factura
            doc.db_set("whatsapp_message_sent", 1)
            doc.db_set("whatsapp_message_id", result.get("message_id"))
            doc.db_set("whatsapp_sent_timestamp", datetime.now())
            doc.db_commit()
            
            frappe.logger().info(f"WhatsApp enviado exitosamente para factura {doc.name}")
        else:
            frappe.logger().error(f"Error enviando WhatsApp para factura {doc.name}: {result.get('error')}")
            # No lanzar excepción para no afectar el proceso DIAN
            
    except Exception as e:
        frappe.logger().error(f"Error enviando WhatsApp para factura {invoice_name}: {str(e)}")
        # No lanzar excepción para no afectar el proceso DIAN


def send_invoice_whatsapp_wrapper(invoice_name):
    """
    Wrapper asíncrono para envío de WhatsApp desde DIAN controller.
    
    Args:
        invoice_name (str): Nombre del documento de factura
    """
    try:
        frappe.logger().info(f"Iniciando envío asíncrono de WhatsApp para factura {invoice_name}")
        send_invoice_whatsapp(invoice_name)
        frappe.logger().info(f"Envío asíncrono de WhatsApp completado para factura {invoice_name}")
    except Exception as e:
        frappe.logger().error(f"Error en wrapper asíncrono de WhatsApp para factura {invoice_name}: {str(e)}")


def payment_entry_on_submit(doc, method=None):
    """
    Hook de submit de Payment Entry para notificación de pagos.
    """
    try:
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        # Verificar si el documento tiene referencia a factura
        if not doc.references:
            return
        
        # Obtener la primera referencia (asumiendo una sola factura por pago)
        reference = doc.references[0]
        
        if reference.reference_doctype == "Sales Invoice":
            invoice_doc = frappe.get_doc("Sales Invoice", reference.reference_name)
            
            if invoice_doc.contact_mobile:
                # Preparar datos del mensaje
                payment_data = {
                    "invoice_number": invoice_doc.name,
                    "customer_name": invoice_doc.customer_name,
                    "payment_amount": doc.paid_amount,
                    "currency": doc.currency,
                    "payment_date": doc.posting_date.strftime('%d/%m/%Y') if doc.posting_date else '',
                    "payment_reference": doc.name
                }
                
                # Enviar mensaje usando plantilla
                from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
                
                result = WhatsAppMessage.send_message(
                    recipient_phone=invoice_doc.contact_mobile,
                    template_name="recordatorio_pago",
                    template_data=payment_data
                )
                
                if result.get("success"):
                    frappe.msgprint(_("✅ Notificación de pago enviada para factura {0}").format(invoice_doc.name), alert=True)
                else:
                    frappe.msgprint(_("❌ Error enviando notificación de pago para factura {0}: {1}").format(invoice_doc.name, result.get("error")), alert=True)
                    
    except Exception as e:
        frappe.log_error(f"Error en hook de Payment Entry: {str(e)}")