"""
WhatsApp Service Layer
Maneja envío de mensajes WhatsApp Business API
"""

from typing import Dict, List, Optional, Any
import frappe
from frappe import _
import logging
import requests

logger = logging.getLogger(__name__)


class WhatsAppServiceLayer:
    """Service Layer para WhatsApp Business API"""
    
    def __init__(self):
        self.api_url = "https://graph.facebook.com/v17.0"
        self.phone_number_id = None
        self.access_token = None
    
    def _get_credentials(self) -> Dict[str, str]:
        """Obtener credenciales de configuración"""
        settings = frappe.get_single("WhatsApp Settings")
        return {
            "phone_number_id": settings.phone_number_id,
            "access_token": settings.get_password("access_token")
        }
    
    def send_template_message(
        self,
        to_number: str,
        template_name: str,
        language_code: str = "es",
        parameters: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enviar mensaje usando template de WhatsApp
        
        Args:
            to_number: Número destino (formato: +57xxxxxxxxxx)
            template_name: Nombre del template aprobado
            language_code: Código de idioma
            parameters: Lista de parámetros para el template
            
        Returns:
            Dict con resultado del envío
        """
        try:
            logger.info(f"Enviando template {template_name} a {to_number}")
            
            creds = self._get_credentials()
            
            # Construir payload
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number.replace("+", ""),
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    }
                }
            }
            
            # Agregar parámetros si existen
            if parameters:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": param}
                            for param in parameters
                        ]
                    }
                ]
            
            # Enviar request
            url = f"{self.api_url}/{creds['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {creds['access_token']}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # Registrar en DocType
            self._log_message(to_number, template_name, result)
            
            logger.info(f"Mensaje enviado exitosamente: {result.get('messages', [{}])[0].get('id')}")
            
            return {
                "success": True,
                "message_id": result.get("messages", [{}])[0].get("id"),
                "timestamp": frappe.utils.now()
            }
            
        except Exception as e:
            logger.error(f"Error enviando mensaje: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": frappe.utils.now()
            }
    
    def send_text_message(
        self,
        to_number: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Enviar mensaje de texto simple
        
        Args:
            to_number: Número destino
            message: Texto del mensaje
            
        Returns:
            Dict con resultado
        """
        try:
            logger.info(f"Enviando texto a {to_number}")
            
            creds = self._get_credentials()
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number.replace("+", ""),
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            url = f"{self.api_url}/{creds['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {creds['access_token']}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            self._log_message(to_number, "text", result)
            
            return {
                "success": True,
                "message_id": result.get("messages", [{}])[0].get("id")
            }
            
        except Exception as e:
            logger.error(f"Error enviando texto: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_document(
        self,
        to_number: str,
        document_url: str,
        filename: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enviar documento (PDF, etc)
        
        Args:
            to_number: Número destino
            document_url: URL del documento
            filename: Nombre del archivo
            caption: Texto adicional
            
        Returns:
            Dict con resultado
        """
        try:
            logger.info(f"Enviando documento a {to_number}")
            
            creds = self._get_credentials()
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number.replace("+", ""),
                "type": "document",
                "document": {
                    "link": document_url,
                    "filename": filename
                }
            }
            
            if caption:
                payload["document"]["caption"] = caption
            
            url = f"{self.api_url}/{creds['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {creds['access_token']}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            self._log_message(to_number, "document", result)
            
            return {
                "success": True,
                "message_id": result.get("messages", [{}])[0].get("id")
            }
            
        except Exception as e:
            logger.error(f"Error enviando documento: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _log_message(self, to_number: str, message_type: str, response: Dict) -> None:
        """Registrar mensaje en DocType para auditoría"""
        try:
            message_log = frappe.get_doc({
                "doctype": "WhatsApp Message Log",
                "to_number": to_number,
                "message_type": message_type,
                "message_id": response.get("messages", [{}])[0].get("id"),
                "status": "sent",
                "timestamp": frappe.utils.now()
            })
            message_log.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            logger.error(f"Error logging mensaje: {str(e)}")


# Singleton
_whatsapp_service = None

def get_whatsapp_service() -> WhatsAppServiceLayer:
    """Obtener instancia singleton"""
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppServiceLayer()
    return _whatsapp_service