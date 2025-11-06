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

@log_whatsapp_event("INFO", "lead_hook")
@handle_whatsapp_errors("lead_hook")
def lead_after_insert(doc, method):
    """Enviar mensaje WhatsApp cuando se crea un nuevo lead"""
    try:
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        # Verificar si el lead tiene teléfono
        if not doc.mobile_no:
            return
        
        # Preparar datos del mensaje
        lead_data = {
            "lead_name": doc.lead_name,
            "company_name": doc.company_name,
            "email_id": doc.email_id,
            "source": doc.source,
            "status": doc.status,
            "created_by": frappe.session.user.full_name
        }
        
        # Enviar mensaje usando plantilla
        from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
        
        result = WhatsAppMessage.send_message(
            recipient_phone=doc.mobile_no,
            template_name="bienvenida_lead",
            template_data=lead_data
        )
        
        if result.get("success"):
            # Registrar referencia en el lead
            doc.db_set("whatsapp_message_sent", 1)
            doc.db_set("whatsapp_message_id", result.get("message_id"))
            doc.db_set("whatsapp_sent_timestamp", datetime.now())
            
            frappe.msgprint(_("✅ Mensaje WhatsApp enviado para lead {0}").format(doc.lead_name), alert=True)
        else:
            frappe.msgprint(_("❌ Error enviando mensaje WhatsApp para lead {0}: {1}").format(doc.lead_name, result.get("error")), alert=True)
            
    except Exception as e:
        frappe.log_error(f"Error en hook de Lead: {str(e)}")

@log_whatsapp_event("INFO", "lead_hook")
@handle_whatsapp_errors("lead_hook")
def lead_on_update(doc, method):
    """Enviar mensaje WhatsApp cuando se actualiza un lead"""
    try:
        # Verificar si WhatsApp está habilitado
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if not whatsapp_settings.enabled:
            return
        
        # Verificar si el lead tiene teléfono
        if not doc.mobile_no:
            return
        
        # Verificar si cambió el estado a "Lead" o "Qualified"
        if doc.has_value_changed("status") and doc.status in ["Lead", "Qualified"]:
            # Preparar datos del mensaje
            lead_data = {
                "lead_name": doc.lead_name,
                "company_name": doc.company_name,
                "new_status": doc.status,
                "updated_by": frappe.session.user.full_name,
                "update_timestamp": datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            
            # Enviar mensaje personalizado
            from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
            
            message_content = f"""🔄 *Actualización de Lead*

Lead: {doc.lead_name}
Empresa: {doc.company_name}
Nuevo estado: {doc.status}
Actualizado por: {lead_data['updated_by']}
Fecha/Hora: {lead_data['update_timestamp']}

Para más información, contacte a su asesor comercial."""
            
            result = WhatsAppMessage.send_message(
                recipient_phone=doc.mobile_no,
                message_content=message_content
            )
            
            if result.get("success"):
                frappe.msgprint(_("✅ Mensaje WhatsApp enviado para actualización de lead {0}").format(doc.lead_name), alert=True)
            else:
                frappe.msgprint(_("❌ Error enviando mensaje WhatsApp para actualización de lead {0}: {1}").format(doc.lead_name, result.get("error")), alert=True)
            
    except Exception as e:
        frappe.log_error(f"Error en hook de actualización de Lead: {str(e)}")