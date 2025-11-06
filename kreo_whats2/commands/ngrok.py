#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

import click
import frappe
from frappe import _
from kreo_whats2.kreo_whats2.utils.ngrok_manager import ngrok_manager
import logging
import sys
import os

# Configuración de logging
logger = logging.getLogger(__name__)

@click.group("ngrok")
def ngrok_cli():
    """Comandos CLI para gestionar túneles Ngrok en KREO WhatsApp"""
    pass

@ngrok_cli.command("start")
@click.option("--port", default=8000, help="Puerto local a exponer (default: 8000)")
@click.option("--protocol", default="http", type=click.Choice(["http", "https"]), 
              help="Protocolo para el túnel (default: http)")
@click.option("--subdomain", help="Subdominio personalizado para el túnel")
@click.option("--authtoken", help="Token de autenticación de Ngrok")
@click.option("--config-path", help="Ruta al archivo de configuración de Ngrok")
def start_ngrok(port, protocol, subdomain, authtoken, config_path):
    """Iniciar túnel Ngrok para desarrollo local"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        # Configurar authtoken si se proporciona
        if authtoken:
            _set_ngrok_authtoken(authtoken)
        
        # Configurar subdominio si se proporciona
        if subdomain:
            _set_ngrok_subdomain(subdomain)
        
        # Iniciar túnel
        logger.info(f"Iniciando túnel Ngrok en puerto {port}")
        url = ngrok_manager.start_ngrok_tunnel(port=port, protocol=protocol)
        
        if url:
            click.echo(f"✅ Túnel Ngrok iniciado exitosamente!")
            click.echo(f"🌐 URL pública: {url}")
            click.echo(f"🔗 Webhook URL: {url}/api/method/kreo_whats2.webhook")
            
            # Verificar si se debe registrar el webhook automáticamente
            _auto_register_webhook(url)
            
            return 0
        else:
            click.echo("❌ Error: No se pudo iniciar el túnel Ngrok")
            return 1
            
    except Exception as e:
        logger.error(f"Error iniciando Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

@ngrok_cli.command("stop")
def stop_ngrok():
    """Detener túnel Ngrok"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        logger.info("Deteniendo túnel Ngrok")
        ngrok_manager.stop_ngrok_tunnel()
        
        click.echo("✅ Túnel Ngrok detenido exitosamente!")
        return 0
        
    except Exception as e:
        logger.error(f"Error deteniendo Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

@ngrok_cli.command("status")
def status_ngrok():
    """Ver estado del túnel Ngrok"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        status = ngrok_manager.get_tunnel_status()
        
        click.echo("📊 Estado del túnel Ngrok:")
        click.echo(f"Estado: {status['status'].upper()}")
        click.echo(f"Mensaje: {status['message']}")
        
        if status['url']:
            click.echo(f"URL: {status['url']}")
            click.echo(f"Webhook: {status['url']}/api/method/kreo_whats2.webhook")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

@ngrok_cli.command("configure")
@click.option("--authtoken", prompt="Ingrese su Ngrok Authtoken", 
              help="Token de autenticación de Ngrok")
@click.option("--subdomain", help="Subdominio personalizado preferido")
@click.option("--save", is_flag=True, default=True, 
              help="Guardar configuración en WhatsApp Settings")
def configure_ngrok(authtoken, subdomain, save):
    """Configurar authtoken y subdominio de Ngrok"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        if save:
            # Guardar en WhatsApp Settings
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if authtoken:
                whatsapp_settings.ngrok_authtoken = authtoken
                logger.info("Authtoken de Ngrok guardado en WhatsApp Settings")
            
            if subdomain:
                whatsapp_settings.ngrok_subdomain = subdomain
                logger.info(f"Subdominio personalizado {subdomain} guardado en WhatsApp Settings")
            
            whatsapp_settings.save()
            frappe.db.commit()
            
            click.echo("✅ Configuración de Ngrok guardada en WhatsApp Settings!")
        else:
            # Solo configurar para esta sesión
            _set_ngrok_authtoken(authtoken)
            if subdomain:
                _set_ngrok_subdomain(subdomain)
            click.echo("✅ Configuración de Ngrok aplicada para esta sesión!")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error configurando Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

@ngrok_cli.command("restart")
@click.option("--port", default=8000, help="Puerto local a exponer (default: 8000)")
@click.option("--protocol", default="http", type=click.Choice(["http", "https"]), 
              help="Protocolo para el túnel (default: http)")
def restart_ngrok(port, protocol):
    """Reiniciar túnel Ngrok"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        logger.info(f"Reiniciando túnel Ngrok en puerto {port}")
        url = ngrok_manager.restart_tunnel(port=port, protocol=protocol)
        
        if url:
            click.echo("✅ Túnel Ngrok reiniciado exitosamente!")
            click.echo(f"🌐 URL pública: {url}")
            click.echo(f"🔗 Webhook URL: {url}/api/method/kreo_whats2.webhook")
            return 0
        else:
            click.echo("❌ Error: No se pudo reiniciar el túnel Ngrok")
            return 1
            
    except Exception as e:
        logger.error(f"Error reiniciando Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

@ngrok_cli.command("logs")
@click.option("--lines", default=50, help="Número de líneas de logs a mostrar (default: 50)")
@click.option("--follow", is_flag=True, default=False, help="Seguir logs en tiempo real")
def logs_ngrok(lines, follow):
    """Mostrar logs de Ngrok"""
    try:
        frappe.init("kreo.localhost")
        frappe.connect()
        
        # Obtener ruta del archivo de logs
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        log_file = f"{whatsapp_settings.log_file_path or 'logs/whatsapp'}/ngrok_manager.log"
        
        if not os.path.exists(log_file):
            click.echo("❌ Archivo de logs no encontrado")
            return 1
        
        click.echo(f"📋 Mostrando últimos {lines} líneas de logs de Ngrok:")
        click.echo("=" * 60)
        
        with open(log_file, 'r') as f:
            if follow:
                # Seguir logs en tiempo real
                import time
                f.seek(0, 2)  # Ir al final del archivo
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line.rstrip())
                    else:
                        time.sleep(0.1)
            else:
                # Mostrar últimas N líneas
                lines_content = f.readlines()
                for line in lines_content[-lines:]:
                    click.echo(line.rstrip())
        
        return 0
        
    except Exception as e:
        logger.error(f"Error mostrando logs de Ngrok: {str(e)}")
        click.echo(f"❌ Error: {str(e)}")
        return 1
    finally:
        frappe.destroy()

def _set_ngrok_authtoken(authtoken):
    """Configurar authtoken de Ngrok"""
    try:
        # Configurar el authtoken usando el comando ngrok
        import subprocess
        subprocess.run(["ngrok", "config", "add-authtoken", authtoken], 
                      check=True, capture_output=True)
        logger.info("Authtoken de Ngrok configurado exitosamente")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error configurando authtoken de Ngrok: {str(e)}")
        raise

def _set_ngrok_subdomain(subdomain):
    """Configurar subdominio personalizado de Ngrok"""
    # Esta función puede ser expandida para manejar subdominios personalizados
    # Actualmente, los subdominios se manejan a través de la configuración de ngrok
    logger.info(f"Subdominio personalizado configurado: {subdomain}")

def _auto_register_webhook(ngrok_url):
    """Registrar webhook automáticamente con Meta API"""
    try:
        whatsapp_settings = frappe.get_single("WhatsApp Settings")
        
        if whatsapp_settings.enabled and whatsapp_settings.auto_register_webhook:
            webhook_url = f"{ngrok_url}/api/method/kreo_whats2.webhook"
            
            # Intentar registrar el webhook
            from kreo_whats2.kreo_whats2.api.webhook_config import WebhookConfig
            webhook_config = WebhookConfig()
            result = webhook_config.register_webhook(webhook_url)
            
            if result.get("success"):
                click.echo("✅ Webhook registrado automáticamente con Meta API!")
            else:
                click.echo(f"⚠️  No se pudo registrar webhook automáticamente: {result.get('error', 'Error desconocido')}")
                
    except Exception as e:
        logger.error(f"Error registrando webhook automáticamente: {str(e)}")
        click.echo(f"⚠️  Error registrando webhook automáticamente: {str(e)}")

if __name__ == "__main__":
    ngrok_cli()