# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
import subprocess
import requests
import logging
import time
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# Intentar importar pyngrok, si no está disponible usar subprocess
try:
    from pyngrok import ngrok, conf
    PYNGROK_AVAILABLE = True
except ImportError:
    PYNGROK_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("pyngrok no está disponible, usando subprocess en su lugar")

class NgrokManager:
    """Gestor de túneles Ngrok para desarrollo local con soporte para pyngrok y subprocess"""
    
    def __init__(self):
        self.ngrok_process = None
        self.ngrok_url = None
        self.tunnel = None
        self._setup_logging()
        self._load_configuration()
    
    def _setup_logging(self):
        """Configurar logging detallado"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if whatsapp_settings.enable_detailed_logging:
                log_level = getattr(logging, whatsapp_settings.log_level.upper(), logging.INFO)
                
                # Configurar handler para archivo
                log_file = f"{whatsapp_settings.log_file_path or 'logs/whatsapp'}/ngrok_manager.log"
                
                # Crear directorio si no existe
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                
                # Configurar file handler
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(log_level)
                
                # Configurar formatter
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(formatter)
                
                # Agregar handler al logger
                logger = logging.getLogger(__name__)
                logger.setLevel(log_level)
                logger.addHandler(file_handler)
                
                logger.info(f"Logging Ngrok Manager configurado en nivel {log_level} hacia {log_file}")
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error configurando logging Ngrok Manager: {str(e)}")
    
    def _load_configuration(self):
        """Cargar configuración de WhatsApp para Ngrok"""
        try:
            self.whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            # Configurar pyngrok si está disponible
            if PYNGROK_AVAILABLE:
                self._configure_pyngrok()
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error cargando configuración: {str(e)}")
            self.whatsapp_settings = None
    
    def _configure_pyngrok(self):
        """Configurar pyngrok con authtoken y subdominio"""
        try:
            if not self.whatsapp_settings:
                return
            
            # Configurar authtoken
            if self.whatsapp_settings.ngrok_authtoken:
                conf.get_default().auth_token = self.whatsapp_settings.ngrok_authtoken
                logger = logging.getLogger(__name__)
                logger.info("pyngrok configurado con authtoken")
            
            # Configurar subdominio
            if self.whatsapp_settings.ngrok_subdomain:
                logger = logging.getLogger(__name__)
                logger.info(f"Subdominio personalizado configurado: {self.whatsapp_settings.ngrok_subdomain}")
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error configurando pyngrok: {str(e)}")
    
    def start_ngrok_tunnel(self, port=8000, protocol="http", subdomain=None, authtoken=None) -> Optional[str]:
        """Iniciar túnel Ngrok para desarrollo local con soporte para pyngrok"""
        try:
            logger = logging.getLogger(__name__)
            
            # Verificar si ya hay un túnel activo
            if self._is_tunnel_active():
                logger.info("Túnel Ngrok ya está activo")
                return self.ngrok_url
            
            # Detener túnel anterior si existe
            self.stop_ngrok_tunnel()
            
            # Usar pyngrok si está disponible y configurado
            if PYNGROK_AVAILABLE and (authtoken or self.whatsapp_settings.ngrok_authtoken):
                return self._start_with_pyngrok(port, protocol, subdomain, authtoken)
            else:
                return self._start_with_subprocess(port, protocol)
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error iniciando túnel Ngrok: {str(e)}")
            self.stop_ngrok_tunnel()
            return None
    
    def _start_with_pyngrok(self, port: int, protocol: str, subdomain: str = None, authtoken: str = None) -> Optional[str]:
        """Iniciar túnel usando pyngrok"""
        try:
            logger = logging.getLogger(__name__)
            
            # Configurar authtoken temporal si se proporciona
            if authtoken:
                conf.get_default().auth_token = authtoken
            
            # Configurar subdominio
            if not subdomain and self.whatsapp_settings.ngrok_subdomain:
                subdomain = self.whatsapp_settings.ngrok_subdomain
            
            # Configurar opciones del túnel
            tunnel_config = {
                "addr": port,
                "proto": protocol,
                "bind_tls": True  # Siempre usar HTTPS
            }
            
            if subdomain:
                tunnel_config["subdomain"] = subdomain
            
            logger.info(f"Iniciando túnel pyngrok en puerto {port} con protocolo {protocol}")
            
            # Crear túnel
            self.tunnel = ngrok.connect(**tunnel_config)
            self.ngrok_url = self.tunnel.public_url
            
            logger.info(f"Túnel pyngrok iniciado exitosamente: {self.ngrok_url}")
            
            # Actualizar configuración de WhatsApp
            self._update_whatsapp_settings()
            
            return self.ngrok_url
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error iniciando túnel con pyngrok: {str(e)}")
            return None
    
    def _start_with_subprocess(self, port: int, protocol: str) -> Optional[str]:
        """Iniciar túnel usando subprocess (método legacy)"""
        try:
            logger = logging.getLogger(__name__)
            
            # Iniciar nuevo túnel
            logger.info(f"Iniciando túnel Ngrok con subprocess en puerto {port}")
            
            # Comando para iniciar Ngrok
            cmd = [
                "ngrok", "http", str(port),
                "--log=stdout",
                "--log-format=json",
                "--bind-tls=true"  # Forzar HTTPS
            ]
            
            # Agregar subdominio si está configurado
            if self.whatsapp_settings and self.whatsapp_settings.ngrok_subdomain:
                cmd.extend(["--subdomain", self.whatsapp_settings.ngrok_subdomain])
            
            # Iniciar proceso
            self.ngrok_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Esperar a que el túnel se inicie
            max_wait_time = 30  # Máximo 30 segundos
            wait_interval = 1  # Verificar cada segundo
            
            for _ in range(max_wait_time):
                # Verificar si el proceso sigue activo
                if self.ngrok_process.poll() is not None:
                    logger.error("Proceso Ngrok terminó inesperadamente")
                    return None
                
                # Intentar obtener URL del túnel
                self.ngrok_url = self._get_ngrok_url()
                
                if self.ngrok_url:
                    logger.info(f"Túnel Ngrok iniciado exitosamente: {self.ngrok_url}")
                    
                    # Actualizar configuración de WhatsApp
                    self._update_whatsapp_settings()
                    
                    return self.ngrok_url
                
                time.sleep(wait_interval)
            
            # Si no se pudo obtener la URL después del tiempo máximo
            logger.error(f"No se pudo obtener URL de Ngrok después de {max_wait_time} segundos")
            self.stop_ngrok_tunnel()
            return None
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error iniciando túnel con subprocess: {str(e)}")
            self.stop_ngrok_tunnel()
            return None
    
    def stop_ngrok_tunnel(self):
        """Detener túnel Ngrok (soporta ambos métodos)"""
        try:
            logger = logging.getLogger(__name__)
            
            if self.tunnel:
                # Detener con pyngrok
                logger.info("Deteniendo túnel pyngrok")
                ngrok.disconnect(self.tunnel.public_url)
                ngrok.kill()
                self.tunnel = None
                self.ngrok_url = None
                logger.info("Túnel pyngrok detenido")
                
            elif self.ngrok_process:
                # Detener con subprocess
                logger.info("Deteniendo túnel Ngrok (subprocess)")
                self.ngrok_process.terminate()
                
                # Esperar a que el proceso termine
                try:
                    self.ngrok_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("Tiempo de espera agotado, forzando terminación")
                    self.ngrok_process.kill()
                
                self.ngrok_process = None
                self.ngrok_url = None
                logger.info("Túnel Ngrok (subprocess) detenido")
            
            # Actualizar configuración de WhatsApp
            self._update_whatsapp_settings()
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error deteniendo túnel Ngrok: {str(e)}")
    
    def _is_tunnel_active(self) -> bool:
        """Verificar si hay un túnel activo"""
        if self.tunnel:
            return True
        if self.ngrok_process and self.ngrok_process.poll() is None:
            return True
        return False
    
    def _get_ngrok_url(self) -> Optional[str]:
        """Obtener URL pública del túnel Ngrok (para subprocess)"""
        try:
            # Consultar API local de Ngrok
            response = requests.get(
                "http://127.0.0.1:4040/api/tunnels",
                timeout=5
            )
            
            if response.status_code == 200:
                tunnels = response.json().get("tunnels", [])
                
                for tunnel in tunnels:
                    if tunnel.get("proto") == "http" and tunnel.get("public_url"):
                        return tunnel.get("public_url")
            
            return None
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo URL de Ngrok: {str(e)}")
            return None
    
    def _update_whatsapp_settings(self):
        """Actualizar configuración de WhatsApp con URL de Ngrok"""
        try:
            if not self.whatsapp_settings:
                return
            
            if self.ngrok_url:
                # Construir URL completa del webhook
                webhook_url = f"{self.ngrok_url}/api/method/kreo_whats2.webhook"
                
                # Actualizar configuración
                frappe.db.set_value("WhatsApp Settings", "ngrok_url", self.ngrok_url)
                frappe.db.set_value("WhatsApp Settings", "webhook_url", webhook_url)
                
                logger = logging.getLogger(__name__)
                logger.info(f"Configuración WhatsApp actualizada con URL Ngrok: {webhook_url}")
            else:
                # Limpiar URL de Ngrok si no hay túnel
                frappe.db.set_value("WhatsApp Settings", "ngrok_url", "")
                logger = logging.getLogger(__name__)
                logger.info("URL de Ngrok eliminada de configuración WhatsApp")
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error actualizando configuración WhatsApp: {str(e)}")
    
    def get_tunnel_status(self) -> Dict[str, Any]:
        """Obtener estado actual del túnel Ngrok"""
        try:
            logger = logging.getLogger(__name__)
            
            if self.tunnel:
                return {
                    "status": "active",
                    "url": self.tunnel.public_url,
                    "method": "pyngrok",
                    "message": "Túnel Ngrok activo (pyngrok)"
                }
            elif self.ngrok_process and self.ngrok_process.poll() is None:
                # Obtener URL actual
                current_url = self._get_ngrok_url()
                
                if current_url:
                    return {
                        "status": "active",
                        "url": current_url,
                        "method": "subprocess",
                        "message": "Túnel Ngrok activo (subprocess)"
                    }
                else:
                    return {
                        "status": "starting",
                        "url": None,
                        "method": "subprocess",
                        "message": "Túnel Ngrok iniciándose"
                    }
            else:
                return {
                    "status": "stopped",
                    "url": None,
                    "method": None,
                    "message": "Túnel Ngrok no está activo"
                }
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo estado de túnel: {str(e)}")
            return {
                "status": "error",
                "url": None,
                "method": None,
                "message": f"Error: {str(e)}"
            }
    
    def restart_tunnel(self, port=8000, protocol="http", subdomain=None, authtoken=None) -> Optional[str]:
        """Reiniciar túnel Ngrok"""
        try:
            logger = logging.getLogger(__name__)
            logger.info("Reiniciando túnel Ngrok")
            self.stop_ngrok_tunnel()
            return self.start_ngrok_tunnel(port, protocol, subdomain, authtoken)
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error reiniciando túnel: {str(e)}")
            return None
    
    def get_tunnel_info(self) -> Dict[str, Any]:
        """Obtener información detallada del túnel"""
        try:
            status = self.get_tunnel_status()
            
            info = {
                "status": status,
                "configuration": {
                    "port": 8000,  # Default
                    "protocol": "http",
                    "subdomain": getattr(self.whatsapp_settings, 'ngrok_subdomain', None) if self.whatsapp_settings else None,
                    "authtoken_configured": bool(getattr(self.whatsapp_settings, 'ngrok_authtoken', None)) if self.whatsapp_settings else False,
                    "pyngrok_available": PYNGROK_AVAILABLE
                },
                "last_updated": datetime.now().isoformat()
            }
            
            return info
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo información del túnel: {str(e)}")
            return {"error": str(e)}
    
    def test_connection(self) -> Dict[str, Any]:
        """Probar conexión del túnel"""
        try:
            logger = logging.getLogger(__name__)
            
            if not self.ngrok_url:
                return {
                    "success": False,
                    "error": "No hay URL de túnel disponible"
                }
            
            # Probar conexión al endpoint de webhook
            webhook_url = f"{self.ngrok_url}/api/method/kreo_whats2.webhook"
            
            try:
                response = requests.get(
                    webhook_url,
                    timeout=10,
                    allow_redirects=False
                )
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "url": webhook_url,
                    "response_time": response.elapsed.total_seconds()
                }
                
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "error": "No se puede conectar al endpoint"
                }
            except requests.exceptions.Timeout:
                return {
                    "success": False,
                    "error": "Tiempo de espera agotado"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error de conexión: {str(e)}"
                }
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error probando conexión: {str(e)}")
            return {
                "success": False,
                "error": f"Excepción: {str(e)}"
            }

# Instancia global del gestor
ngrok_manager = NgrokManager()
