# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
import json
import requests
import redis
from datetime import datetime, timedelta
import logging
import time

class WhatsAppSettings(Document):
    """Configuración de WhatsApp Business API para KREO Colombia"""
    
    def validate(self):
        """Validar configuración antes de guardar"""
        if self.enabled and not self.access_token:
            frappe.throw(_("Access Token es requerido cuando WhatsApp está habilitado"))
        
        if self.enabled and not self.phone_number_id:
            frappe.throw(_("Phone Number ID es requerido cuando WhatsApp está habilitado"))
        
        if self.enabled and not self.webhook_verify_token:
            frappe.throw(_("Webhook Verify Token es requerido cuando WhatsApp está habilitado"))
        
        # Validar formato de plantillas
        self._validate_template_format(self.factura_emitida_template, "factura")
        self._validate_template_format(self.recordatorio_pago_template, "recordatorio")
        self._validate_template_format(self.bienvenida_lead_template, "bienvenida")
        
        # Validar límites de rate limiting
        if self.rate_limit_per_second < 1 or self.rate_limit_per_second > 50:
            frappe.throw(_("Rate limit debe estar entre 1 y 50 mensajes por segundo"))
        
        if self.concurrent_messages_limit < 10 or self.concurrent_messages_limit > 1000:
            frappe.throw(_("Límite concurrente debe estar entre 10 y 1000 mensajes"))
    
    def _validate_template_format(self, template, template_type):
        """Validar formato de plantilla"""
        if not template:
            return
        
        # Variables requeridas por tipo de plantilla
        required_vars = {
            "factura": ["invoice_number", "amount", "currency", "due_date", "invoice_url"],
            "recordatorio": ["invoice_number", "amount", "currency", "due_date", "payment_url"],
            "bienvenida": ["product_name", "contact_name", "phone"]
        }
        
        if template_type in required_vars:
            for var in required_vars[template_type]:
                if f"{{{var}}}" not in template:
                    frappe.throw(_("Plantilla de {0} debe incluir la variable {{{1}}}").format(template_type, var))
    
    def on_update(self):
        """Actualizar configuración cuando se modifica"""
        if self.has_value_changed("enabled"):
            if self.enabled:
                self._setup_webhook()
                self._verify_meta_credentials()
            else:
                self._disable_webhook()
        
        # Manejar cambios en configuración de Ngrok
        if (self.has_value_changed("ngrok_authtoken") or
            self.has_value_changed("ngrok_subdomain") or
            self.has_value_changed("auto_register_webhook")):
            self._handle_ngrok_config_change()
    
    def _handle_ngrok_config_change(self):
        """Manejar cambios en configuración de Ngrok"""
        try:
            if self.ngrok_authtoken:
                frappe.msgprint(_("✅ Authtoken de Ngrok configurado exitosamente"), alert=True)
            
            if self.ngrok_subdomain:
                frappe.msgprint(_("✅ Subdominio personalizado de Ngrok configurado: {0}").format(self.ngrok_subdomain), alert=True)
                
        except Exception as e:
            frappe.log_error(f"Error manejando cambio de configuración de Ngrok: {str(e)}")
    
    def _setup_webhook(self):
        """Configurar webhook en Meta Business API"""
        try:
            webhook_url = self.webhook_url or f"https://kreo.localhost/api/method/kreo_whats2.webhook"
            verify_token = self.webhook_verify_token or "kreo_whatsapp_verify_2024"
            
            # Registrar webhook en Meta Business API
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "webhook_url": webhook_url,
                "verify_token": verify_token,
                "fields": ["messages", "status", "errors"]
            }
            
            response = requests.post(
                f"https://graph.facebook.com/v18.0/{self.phone_number_id}/subscribed_apps",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                # Actualizar estado de registro
                self.webhook_registered = True
                self.webhook_registration_date = datetime.now()
                self.save()
                
                frappe.msgprint(_("Webhook configurado exitosamente"), alert=True)
            else:
                frappe.msgprint(_("Error configurando webhook: {0}").format(response.text), alert=True)
                
        except Exception as e:
            frappe.msgprint(_("Error en configuración de webhook: {0}").format(str(e)), alert=True)
    
    def _disable_webhook(self):
        """Desactivar webhook"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.delete(
                f"https://graph.facebook.com/v18.0/{self.phone_number_id}/subscribed_apps",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                # Actualizar estado de registro
                self.webhook_registered = False
                self.webhook_registration_date = None
                self.save()
                
                frappe.msgprint(_("Webhook desactivado exitosamente"), alert=True)
            else:
                frappe.msgprint(_("Error desactivando webhook: {0}").format(response.text), alert=True)
                
        except Exception as e:
            frappe.msgprint(_("Error desactivando webhook: {0}").format(str(e)), alert=True)
    
    def _verify_meta_credentials(self):
        """Verificar credenciales con Meta Business API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"https://graph.facebook.com/v18.0/{self.phone_number_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("display_phone_number"):
                    frappe.msgprint(_("Credenciales verificadas exitosamente para {0}").format(data["display_phone_number"]), alert=True)
                    return True
                else:
                    frappe.msgprint(_("Número de teléfono no verificado en Meta"), alert=True)
                    return False
            else:
                frappe.msgprint(_("Error verificando credenciales: {0}").format(response.text), alert=True)
                return False
                
        except Exception as e:
            frappe.msgprint(_("Error en verificación de credenciales: {0}").format(str(e)), alert=True)
            return False
    
    @frappe.whitelist()
    def test_connection(self):
        """Probar conexión con Meta Business API"""
        if not self.enabled:
            frappe.throw(_("WhatsApp no está habilitado"))
        
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Enviar mensaje de prueba
            test_payload = {
                "messaging_product": "whatsapp",
                "to": f"whatsapp:{self.phone_number_id}",
                "type": "template",
                "template": {
                    "name": "test_connection",
                    "language": "es",
                    "components": [
                        {
                            "type": "body",
                            "text": "🧪 Mensaje de prueba desde KREO WhatsApp - Conexión exitosa"
                        }
                    ]
                }
            }
            
            response = requests.post(
                f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages",
                headers=headers,
                json=test_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                frappe.msgprint(_("✅ Conexión exitosa con Meta Business API"), alert=True)
                return {"success": True, "message": "Conexión establecida"}
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                frappe.msgprint(_("❌ Error en conexión: {0}").format(error_msg), alert=True)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            frappe.msgprint(_("❌ Excepción en conexión: {0}").format(str(e)), alert=True)
            return {"success": False, "error": str(e)}
    
    @frappe.whitelist()
    def get_rate_limit_status(self):
        """Obtener estado actual del rate limiting"""
        try:
            redis_client = self._get_redis_client()
            current_usage = redis_client.get(f"whatsapp_rate_limit:{datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            return {
                "current_usage": int(current_usage or 0),
                "limit_per_second": self.rate_limit_per_second,
                "concurrent_limit": self.concurrent_messages_limit,
                "queue_size": self.queue_size_limit,
                "reset_time": (datetime.now() + timedelta(seconds=60)).isoformat()
            }
            
        except Exception as e:
            frappe.log_error(f"Error obteniendo status de rate limiting: {str(e)}")
            return {"error": str(e)}
    
    def _get_redis_client(self):
        """Obtener cliente Redis para rate limiting"""
        try:
            import redis
            return redis.from_url(self.redis_queue_url or "redis://redis-queue:6379/1")
        except Exception as e:
            frappe.log_error(f"Error conectando a Redis: {str(e)}")
            return None
    
    @frappe.whitelist()
    def health_check(self):
        """Verificación de salud del servicio WhatsApp"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "service": "WhatsApp Business API",
            "status": "healthy",
            "checks": []
        }
        
        # Verificar credenciales
        if self.enabled:
            try:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.get(
                    f"https://graph.facebook.com/v18.0/{self.phone_number_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    status["checks"].append({
                        "name": "meta_api_connection",
                        "status": "pass",
                        "message": "Conexión con Meta API exitosa"
                    })
                else:
                    status["checks"].append({
                        "name": "meta_api_connection",
                        "status": "fail",
                        "message": f"Error {response.status_code}: {response.text[:100]}"
                    })
                    status["status"] = "unhealthy"
                    
            except Exception as e:
                status["checks"].append({
                    "name": "meta_api_connection",
                    "status": "fail",
                    "message": f"Excepción: {str(e)}"
                })
                status["status"] = "unhealthy"
        else:
            status["checks"].append({
                "name": "service_enabled",
                "status": "fail",
                "message": "Servicio WhatsApp no está habilitado"
            })
            status["status"] = "disabled"
        
        # Verificar conexión Redis
        try:
            redis_client = self._get_redis_client()
            if redis_client:
                redis_client.ping()
                status["checks"].append({
                    "name": "redis_connection",
                    "status": "pass",
                    "message": "Conexión Redis exitosa"
                })
            else:
                status["checks"].append({
                    "name": "redis_connection",
                    "status": "fail",
                    "message": "No se puede conectar a Redis"
                })
                status["status"] = "unhealthy"
        except Exception as e:
            status["checks"].append({
                "name": "redis_connection",
                "status": "fail",
                "message": f"Error Redis: {str(e)}"
            })
            status["status"] = "unhealthy"
        
        # Verificar estado de Ngrok
        try:
            from kreo_whats2.kreo_whats2.utils.ngrok_manager import ngrok_manager
            ngrok_status = ngrok_manager.get_tunnel_status()
            
            if ngrok_status["status"] == "active":
                status["checks"].append({
                    "name": "ngrok_tunnel",
                    "status": "pass",
                    "message": f"Túnel Ngrok activo: {ngrok_status['url']}"
                })
            elif ngrok_status["status"] == "stopped":
                status["checks"].append({
                    "name": "ngrok_tunnel",
                    "status": "info",
                    "message": "Túnel Ngrok no está activo (desarrollo local)"
                })
            else:
                status["checks"].append({
                    "name": "ngrok_tunnel",
                    "status": "warning",
                    "message": f"Estado de Ngrok: {ngrok_status['message']}"
                })
                
        except Exception as e:
            status["checks"].append({
                "name": "ngrok_tunnel",
                "status": "fail",
                "message": f"Error verificando Ngrok: {str(e)}"
            })
            status["status"] = "unhealthy"
        
        # Verificar webhook
        if self.webhook_registered:
            status["checks"].append({
                "name": "webhook_registered",
                "status": "pass",
                "message": f"Webhook registrado: {self.webhook_url}"
            })
        else:
            status["checks"].append({
                "name": "webhook_registered",
                "status": "info",
                "message": "Webhook no registrado (solo para producción)"
            })
        
        return status
    
    @frappe.whitelist()
    def test_ngrok_connection(self):
        """Probar conexión del túnel Ngrok"""
        try:
            from kreo_whats2.kreo_whats2.utils.ngrok_manager import ngrok_manager
            
            result = ngrok_manager.test_connection()
            
            if result.get("success"):
                frappe.msgprint(_(
                    "✅ Conexión Ngrok exitosa!<br>"
                    "URL: {0}<br>"
                    "Código de estado: {1}<br>"
                    "Tiempo de respuesta: {2}s"
                ).format(
                    result.get("url", "N/A"),
                    result.get("status_code", "N/A"),
                    result.get("response_time", "N/A")
                ), alert=True)
                return result
            else:
                frappe.msgprint(_(
                    "❌ Error en conexión Ngrok: {0}"
                ).format(result.get("error", "Error desconocido")), alert=True)
                return result
                
        except Exception as e:
            frappe.log_error(f"Error probando conexión Ngrok: {str(e)}")
            frappe.msgprint(_("❌ Excepción probando Ngrok: {0}").format(str(e)), alert=True)
            return {"success": False, "error": str(e)}
    
    @frappe.whitelist()
    def get_ngrok_status(self):
        """Obtener estado del túnel Ngrok"""
        try:
            from kreo_whats2.kreo_whats2.utils.ngrok_manager import ngrok_manager
            
            status = ngrok_manager.get_tunnel_info()
            
            return {
                "success": True,
                "data": status
            }
            
        except Exception as e:
            frappe.log_error(f"Error obteniendo estado Ngrok: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @frappe.whitelist()
    def register_webhook_automatically(self):
        """Registrar webhook automáticamente usando URL de Ngrok"""
        try:
            if not self.ngrok_url:
                frappe.throw(_("No hay URL de Ngrok disponible. Inicie el túnel primero."))
            
            from kreo_whats2.kreo_whats2.api.webhook_config import webhook_config
            
            webhook_url = f"{self.ngrok_url}/api/method/kreo_whats2.webhook"
            result = webhook_config.register_webhook(webhook_url)
            
            if result.get("success"):
                frappe.msgprint(_("✅ Webhook registrado automáticamente con éxito!"), alert=True)
                return result
            else:
                frappe.msgprint(_("❌ Error registrando webhook: {0}").format(result.get("error", "Error desconocido")), alert=True)
                return result
                
        except Exception as e:
            frappe.log_error(f"Error registrando webhook automáticamente: {str(e)}")
            frappe.msgprint(_("❌ Excepción registrando webhook: {0}").format(str(e)), alert=True)
            return {"success": False, "error": str(e)}