# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
import json
import requests
from datetime import datetime
import logging

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import log_whatsapp_event, handle_whatsapp_errors
    ADVANCED_LOGGING_AVAILABLE = True
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False

class WhatsAppMessage(Document):
    """Registro de mensajes enviados/recibidos vía WhatsApp"""
    
    def validate(self):
        """Validar mensaje antes de guardar"""
        if self.message_type == "Outgoing" and not self.recipient:
            frappe.throw(_("Destinatario es requerido para mensajes salientes"))
        
        if self.message_type == "Incoming" and not self.sender_phone:
            frappe.throw(_("Teléfono remitente es requerido para mensajes entrantes"))
        
        if self.template_used and not self.template_name:
            frappe.throw(_("Nombre de plantilla es requerido cuando se usa plantilla"))
    
    def before_save(self):
        """Acciones antes de guardar"""
        # Generar ID único si no existe
        if not self.wa_message_id:
            self.wa_message_id = f"wa_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{frappe.generate_hash(length=8)}"
        
        # Establecer timestamp de envío
        if self.message_type == "Outgoing" and not self.sent_timestamp:
            self.sent_timestamp = datetime.now()
    
    def after_insert(self):
        """Acciones después de insertar"""
        # Actualizar contador de mensajes
        self._update_message_counters()
        
        # Enviar a Redis Queue si es mensaje saliente
        if self.message_type == "Outgoing":
            self._enqueue_message()
    
    def _update_message_counters(self):
        """Actualizar contadores de mensajes"""
        try:
            # Actualizar estadísticas diarias
            today = datetime.now().strftime('%Y-%m-%d')
            stats = frappe.db.get_value("WhatsApp Message Stats", {"date": today}, "stats") or {}
            
            stats[f"{self.message_type.lower()}_count"] = stats.get(f"{self.message_type.lower()}_count", 0) + 1
            
            # Guardar o actualizar estadísticas
            if frappe.db.exists("WhatsApp Message Stats", {"date": today}):
                frappe.db.set_value("WhatsApp Message Stats", {"date": today}, "stats", json.dumps(stats))
            else:
                stats_doc = frappe.new_doc("WhatsApp Message Stats")
                stats_doc.date = today
                stats_doc.stats = json.dumps(stats)
                stats_doc.insert()
                
        except Exception as e:
            frappe.log_error(f"Error actualizando contadores: {str(e)}")
    
    def _enqueue_message(self):
        """Encolar mensaje para envío asíncrono"""
        try:
            # Obtener configuración de WhatsApp
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                return
            
            # Conectar a Redis Queue
            import redis
            redis_client = redis.from_url(whatsapp_settings.redis_queue_url or "redis://redis-queue:6379/1")
            
            # Preparar payload para cola
            queue_data = {
                "message_id": self.name,
                "recipient": self.recipient_phone,
                "content": self.message_content,
                "template_name": self.template_name,
                "template_data": self.template_data,
                "sender": self.sender,
                "timestamp": self.sent_timestamp.isoformat(),
                "retry_count": 0,
                "max_retries": whatsapp_settings.max_retry_attempts or 3
            }
            
            # Agregar a la cola
            redis_client.lpush(
                whatsapp_settings.redis_queue_name or "kreo_whatsapp_queue",
                json.dumps(queue_data)
            )
            
            # Actualizar estado a "Queued"
            self.status = "Queued"
            self.save()
            
            frappe.logger.info(f"Mensaje {self.name} encolado para envío")
            
        except Exception as e:
            frappe.log_error(f"Error encolando mensaje: {str(e)}")
            self.status = "Queue Failed"
            self.save()
    
    @frappe.whitelist()
    @log_whatsapp_event("INFO", "whatsapp_message")
    @handle_whatsapp_errors("whatsapp_message")
    def send_message(self, recipient_phone, message_content, template_name=None, template_data=None):
        """Enviar mensaje vía WhatsApp"""
        try:
            # Obtener configuración
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if not whatsapp_settings.enabled:
                return {"success": False, "error": "WhatsApp no está habilitado"}
            
            # Verificar rate limiting
            rate_status = whatsapp_settings.get_rate_limit_status()
            if rate_status.get("current_usage", 0) >= rate_status.get("limit_per_second", 10):
                return {"success": False, "error": "Rate limit excedido"}
            
            # Crear registro del mensaje
            message_doc = frappe.new_doc("WhatsApp Message")
            message_doc.message_type = "Outgoing"
            message_doc.direction = "Outbound"
            message_doc.recipient_phone = recipient_phone
            message_doc.message_content = message_content
            message_doc.sender = frappe.session.user
            message_doc.template_name = template_name
            message_doc.template_data = json.dumps(template_data) if template_data else None
            message_doc.template_used = 1 if template_name else 0
            message_doc.source = "Frappe CRM"
            message_doc.campaign_name = "KREO Automatización"
            message_doc.auto_retry = 1
            message_doc.retry_interval = whatsapp_settings.retry_interval or 300
            message_doc.insert()
            
            return {"success": True, "message_id": message_doc.name}
            
        except Exception as e:
            frappe.log_error(f"Error enviando mensaje: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @frappe.whitelist()
    @log_whatsapp_event("INFO", "whatsapp_message")
    @handle_whatsapp_errors("whatsapp_message")
    def process_webhook(self, webhook_data):
        """Procesar webhook entrante desde WhatsApp"""
        try:
            # Verificar webhook
            if not self._verify_webhook(webhook_data):
                return {"success": False, "error": "Verificación de webhook fallida"}
            
            # Procesar mensajes entrantes
            if webhook_data.get("object") == "page":
                for entry in webhook_data.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("field") == "messages":
                            message_data = change.get("value", {})
                            if message_data.get("messages"):
                                for message in message_data.get("messages", []):
                                    self._process_incoming_message(message)
            
            return {"success": True, "processed": len(webhook_data.get("entry", []))}
            
        except Exception as e:
            frappe.log_error(f"Error procesando webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _verify_webhook(self, webhook_data):
        """Verificar webhook"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            # Verificar token
            if webhook_data.get("hub.verify_token") != whatsapp_settings.webhook_verify_token:
                return False
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Error verificando webhook: {str(e)}")
            return False
    
    def _process_incoming_message(self, message_data):
        """Procesar mensaje entrante"""
        try:
            # Extraer información del mensaje
            message_info = message_data.get("message", {})
            contacts = message_data.get("contacts", [])
            
            if not contacts:
                return
            
            contact = contacts[0] if contacts else {}
            phone_number = contact.get("wa_id", "").replace("whatsapp:", "")
            
            # Crear registro del mensaje entrante
            message_doc = frappe.new_doc("WhatsApp Message")
            message_doc.message_type = "Incoming"
            message_doc.direction = "Inbound"
            message_doc.sender_phone = phone_number
            message_doc.recipient = "System"
            message_doc.message_content = message_info.get("text", "")
            message_doc.wa_message_id = message_data.get("id", "")
            message_doc.delivery_status = "Received"
            message_doc.read_timestamp = datetime.now()
            message_doc.source = "WhatsApp Webhook"
            message_doc.insert()
            
            # Procesar comandos automáticos
            self._process_auto_commands(message_info.get("text", ""), phone_number)
            
        except Exception as e:
            frappe.log_error(f"Error procesando mensaje entrante: {str(e)}")
    
    def _process_auto_commands(self, message_text, sender_phone):
        """Procesar comandos automáticos"""
        try:
            # Comando de estado
            if message_text.lower() in ["estado", "status", "consultar"]:
                self._send_status_response(sender_phone)
                return
            
            # Comando de ayuda
            if message_text.lower() in ["ayuda", "help", "comandos"]:
                self._send_help_response(sender_phone)
                return
                
        except Exception as e:
            frappe.log_error(f"Error procesando comando automático: {str(e)}")
    
    def _send_status_response(self, recipient_phone):
        """Enviar respuesta de estado"""
        try:
            # Obtener estadísticas
            stats = frappe.db.get_all("WhatsApp Message", 
                filters={"message_type": "Outgoing", "status": "Sent"}, 
                fields=["count(name)"], 
                as_list=True
            )
            
            total_sent = sum(row.get("count", 0) for row in stats)
            
            response_text = f"📊 *Estado KREO WhatsApp*\n\nMensajes enviados hoy: {total_sent}\n\n✅ Servicio operativo"
            
            # Enviar respuesta
            self.send_message(recipient_phone, response_text)
            
        except Exception as e:
            frappe.log_error(f"Error enviando respuesta de estado: {str(e)}")
    
    def _send_help_response(self, recipient_phone):
        """Enviar respuesta de ayuda"""
        try:
            help_text = f"""🤖 *Comandos KREO WhatsApp*
            
📋 *Comandos disponibles:*
• `estado` - Consultar estado del servicio
• `ayuda` - Mostrar esta ayuda

💡 *Ejemplos:*
• estado
• ayuda

🔧 *Soporte:*
Para asistencia adicional, contacte a soporte@kreo.com.co"""
            
            # Enviar respuesta
            self.send_message(recipient_phone, help_text)
            
        except Exception as e:
            frappe.log_error(f"Error enviando respuesta de ayuda: {str(e)}")
    
    @log_whatsapp_event("INFO", "whatsapp_message")
    @handle_whatsapp_errors("whatsapp_message")
    def update_delivery_status(self, wa_message_id, delivery_status, error_details=None):
        """Actualizar estado de entrega de mensaje"""
        try:
            # Buscar mensaje
            message_doc = frappe.get_doc("WhatsApp Message", wa_message_id)
            
            if not message_doc:
                return {"success": False, "error": "Mensaje no encontrado"}
            
            # Actualizar estado
            message_doc.delivery_status = delivery_status
            message_doc.read_timestamp = datetime.now() if delivery_status == "Read" else message_doc.read_timestamp
            
            if error_details:
                message_doc.error_message = json.dumps(error_details)
                message_doc.error_code = error_details.get("code", "UNKNOWN")
            
            message_doc.save()
            
            return {"success": True, "message_id": wa_message_id}
            
        except Exception as e:
            frappe.log_error(f"Error actualizando estado: {str(e)}")
            return {"success": False, "error": str(e)}