"""
Notification Service
Gestiona notificaciones automáticas por WhatsApp
"""

from typing import Dict, List, Optional, Any
import frappe
from frappe import _
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NotificationService:
    """Servicio de notificaciones automáticas"""
    
    def __init__(self):
        self.whatsapp_service = None
    
    def get_whatsapp_service(self):
        """Lazy loading del servicio WhatsApp"""
        if not self.whatsapp_service:
            from .whatsapp_service import get_whatsapp_service
            self.whatsapp_service = get_whatsapp_service()
        return self.whatsapp_service
    
    def send_invoice_notification(
        self,
        invoice_doc: Any,
        notification_type: str = "created"
    ) -> Dict[str, Any]:
        """
        Enviar notificación de factura
        
        Args:
            invoice_doc: Documento de factura
            notification_type: Tipo (created/paid/overdue)
            
        Returns:
            Dict con resultado
        """
        try:
            logger.info(f"Enviando notificación de factura {invoice_doc.name}")
            
            # Obtener número de teléfono del cliente
            customer = frappe.get_doc("Customer", invoice_doc.customer)
            phone = self._get_customer_phone(customer)
            
            if not phone:
                return {
                    "success": False,
                    "error": "Cliente no tiene número de teléfono"
                }
            
            # Seleccionar template según tipo
            templates = {
                "created": "invoice_created",
                "paid": "invoice_paid",
                "overdue": "invoice_overdue"
            }
            
            template_name = templates.get(notification_type, "invoice_created")
            
            # Preparar parámetros
            parameters = [
                customer.customer_name,
                invoice_doc.name,
                str(invoice_doc.grand_total),
                invoice_doc.currency or "COP"
            ]
            
            # Enviar mensaje
            whatsapp = self.get_whatsapp_service()
            result = whatsapp.send_template_message(
                phone,
                template_name,
                "es",
                parameters
            )
            
            logger.info(f"Notificación de factura enviada: {result.get('message_id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enviando notificación: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_payment_reminder(
        self,
        invoice_doc: Any,
        days_overdue: int = 0
    ) -> Dict[str, Any]:
        """
        Enviar recordatorio de pago
        
        Args:
            invoice_doc: Documento de factura
            days_overdue: Días de vencimiento
            
        Returns:
            Dict con resultado
        """
        try:
            logger.info(f"Enviando recordatorio de pago para {invoice_doc.name}")
            
            customer = frappe.get_doc("Customer", invoice_doc.customer)
            phone = self._get_customer_phone(customer)
            
            if not phone:
                return {
                    "success": False,
                    "error": "Cliente no tiene número de teléfono"
                }
            
            # Mensaje personalizado según días de vencimiento
            if days_overdue == 0:
                message = f"Estimado {customer.customer_name}, su factura {invoice_doc.name} vence hoy. Monto: {invoice_doc.grand_total} {invoice_doc.currency}. Por favor realizar el pago."
            elif days_overdue > 0:
                message = f"Estimado {customer.customer_name}, su factura {invoice_doc.name} está vencida hace {days_overdue} días. Monto: {invoice_doc.grand_total} {invoice_doc.currency}. Por favor contactarnos."
            else:
                message = f"Estimado {customer.customer_name}, recordatorio: su factura {invoice_doc.name} vence en {abs(days_overdue)} días. Monto: {invoice_doc.grand_total} {invoice_doc.currency}."
            
            # Enviar mensaje de texto
            whatsapp = self.get_whatsapp_service()
            result = whatsapp.send_text_message(phone, message)
            
            logger.info(f"Recordatorio enviado: {result.get('message_id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_document_notification(
        self,
        recipient: str,
        document_name: str,
        document_url: str,
        doctype: str = "Invoice"
    ) -> Dict[str, Any]:
        """
        Enviar documento por WhatsApp
        
        Args:
            recipient: Número de teléfono
            document_name: Nombre del documento
            document_url: URL del documento
            doctype: Tipo de documento
            
        Returns:
            Dict con resultado
        """
        try:
            logger.info(f"Enviando documento {document_name} a {recipient}")
            
            # Determinar nombre de archivo
            filename = f"{doctype}_{document_name}.pdf"
            
            # Mensaje de acompañamiento
            caption = f"Documento {doctype}: {document_name}"
            
            # Enviar documento
            whatsapp = self.get_whatsapp_service()
            result = whatsapp.send_document(
                recipient,
                document_url,
                filename,
                caption
            )
            
            logger.info(f"Documento enviado: {result.get('message_id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enviando documento: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def schedule_automatic_reminders(self) -> Dict[str, Any]:
        """
        Programar recordatorios automáticos para facturas vencidas
        
        Returns:
            Dict con estadísticas de envío
        """
        try:
            logger.info("Iniciando envío de recordatorios automáticos")
            
            # Buscar facturas vencidas
            today = datetime.now().date()
            overdue_invoices = frappe.get_all(
                "Sales Invoice",
                filters={
                    "status": ["!=", "Paid"],
                    "due_date": ["<", today],
                    "docstatus": 1
                },
                fields=["name", "customer", "due_date", "grand_total"]
            )
            
            sent_count = 0
            failed_count = 0
            
            for invoice in overdue_invoices:
                try:
                    invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
                    days_overdue = (today - invoice.due_date).days
                    
                    result = self.send_payment_reminder(invoice_doc, days_overdue)
                    
                    if result.get("success"):
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error procesando factura {invoice.name}: {str(e)}")
                    failed_count += 1
            
            logger.info(f"Recordatorios enviados: {sent_count}, fallidos: {failed_count}")
            
            return {
                "success": True,
                "sent": sent_count,
                "failed": failed_count,
                "total": len(overdue_invoices)
            }
            
        except Exception as e:
            logger.error(f"Error en envío automático: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_customer_phone(self, customer: Any) -> Optional[str]:
        """Obtener número de teléfono del cliente"""
        # Intentar obtener de custom field o campo móvil
        phone = customer.get("mobile_no") or customer.get("phone")
        
        if phone:
            # Normalizar formato
            phone = phone.strip().replace(" ", "").replace("-", "")
            if not phone.startswith("+"):
                phone = "+57" + phone  # Asumir Colombia si no tiene código
            
        return phone


# Singleton
_notification_service = None

def get_notification_service() -> NotificationService:
    """Obtener instancia singleton"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service