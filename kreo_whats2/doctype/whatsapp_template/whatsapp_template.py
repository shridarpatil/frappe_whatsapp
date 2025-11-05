#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Doctype para gestión de plantillas de WhatsApp
Implementa validación, almacenamiento y gestión de plantillas de mensajes
"""

import frappe
from frappe import _
import json
import logging
from datetime import datetime
from kreo_whats2.kreo_whats2.api.template_renderer import template_renderer
from kreo_whats2.kreo_whats2.utils.logging_manager import (
    log_whatsapp_template_event,
    handle_whatsapp_template_errors,
    get_logger
)

logger = get_logger("whatsapp_template")

def validate_template_name(template_name):
    """Validar formato del nombre de plantilla"""
    import re
    if not re.match(r'^[a-z0-9_]+$', template_name):
        frappe.throw(
            _("El nombre de la plantilla solo puede contener letras minúsculas, números y guiones bajos"),
            frappe.ValidationError
        )

def extract_variables_from_html(html_content):
    """Extraer variables de Jinja2 desde contenido HTML"""
    import re
    
    # Patrones para extraer variables de Jinja2
    patterns = [
        r'\{\{\s*(\w+)\s*\}\}',  # {{ variable }}
        r'\{\%\s*if\s+(\w+)\s*\%\}',  # {% if variable %}
        r'\{\%\s*for\s+(\w+)\s+in\s+\w+\s*\%\}',  # {% for item in list %}
    ]
    
    variables = set()
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        variables.update(matches)
    
    return list(variables)

class WhatsAppTemplate:
    """Controlador del DocType WhatsApp Template"""
    
    @log_whatsapp_template_event("INFO", "template_operation")
    @handle_whatsapp_template_errors("template_operation")
    def validate(self):
        """Validar el documento antes de guardar"""
        try:
            logger.info("Iniciando validación de plantilla", extra={
                'template_name': self.template_name,
                'template_type': self.template_type,
                'category': self.category
            })
            
            # Validar nombre de plantilla
            if self.template_name:
                validate_template_name(self.template_name)
            
            # Validar contenido HTML
            if self.content_html:
                self._validate_html_content()
            
            # Extraer y actualizar variables
            if self.content_html:
                self._update_variables()
            
            # Validar botones según categoría
            self._validate_buttons()
            
            logger.info("Validación de plantilla completada exitosamente")
            
        except Exception as e:
            logger.error(f"Error validando plantilla {self.template_name}: {str(e)}", exc_info=True)
            frappe.throw(str(e))
    
    def _validate_html_content(self):
        """Validar contenido HTML de la plantilla"""
        from bleach import clean
        
        # Verificar longitud máxima
        if len(self.content_html) > 50000:  # 50KB máximo
            frappe.throw(_("El contenido HTML excede el límite de 50KB"))
        
        # Verificar estructura básica
        if '<html' not in self.content_html.lower():
            frappe.msgprint(
                _("Se recomienda incluir la estructura HTML completa para mejor compatibilidad"),
                alert=True
            )
        
        # Verificar variables de Jinja2
        variables = extract_variables_from_html(self.content_html)
        if not variables:
            frappe.msgprint(
                _("No se encontraron variables de Jinja2 en la plantilla. Considere usar {{variable}} para datos dinámicos"),
                alert=True
            )
    
    def _update_variables(self):
        """Actualizar tabla de variables basado en contenido HTML"""
        # Limpiar variables existentes
        self.set('variables', [])
        
        # Extraer nuevas variables
        variables = extract_variables_from_html(self.content_html)
        
        # Agregar variables a la tabla
        for var_name in variables:
            self.append('variables', {
                'variable_name': var_name,
                'description': f'Variable dinámica: {var_name}',
                'data_type': 'Text',
                'required': var_name in self._get_required_variables()
            })
        
        # Actualizar variables requeridas
        self.required_variables = ', '.join(self._get_required_variables())
    
    def _get_required_variables(self):
        """Obtener variables requeridas según tipo de plantilla"""
        required_map = {
            'Factura': ['customer_name', 'invoice_number', 'amount', 'currency'],
            'Recordatorio': ['customer_name', 'invoice_number', 'amount', 'currency', 'due_date'],
            'Bienvenida': ['lead_name', 'company_name', 'support_email'],
            'General': [],
            'Promoción': [],
            'Soporte': []
        }
        
        return required_map.get(self.template_type, [])
    
    def _validate_buttons(self):
        """Validar botones según categoría de Meta"""
        if not self.buttons:
            return
        
        # Meta tiene límites de botones según categoría
        max_buttons = 10  # Límite general
        
        if self.category == 'AUTHENTICATION':
            max_buttons = 1
        
        if len(self.buttons) > max_buttons:
            frappe.throw(
                _(f"La categoría {self.category} permite máximo {max_buttons} botones")
            )
        
        # Validar tipos de botones
        for btn in self.buttons:
            if btn.button_type == 'PHONE_NUMBER' and not btn.phone_number:
                frappe.throw(_("Botón de llamada requiere número de teléfono"))
            
            if btn.button_type == 'URL' and not btn.url:
                frappe.throw(_("Botón de URL requiere enlace"))
    
    def on_update(self):
        """Acciones al actualizar el documento"""
        # Limpiar cache de plantillas
        try:
            template_renderer.clear_template_cache(self.template_name)
            frappe.msgprint(
                _("Cache de plantilla limpiado exitosamente"),
                alert=True
            )
        except Exception as e:
            frappe.msgprint(
                _("Error limpiando cache de plantilla"),
                alert=True
            )
            logger.error(f"Error limpiando cache: {str(e)}")
    
    def on_submit(self):
        """Acciones al enviar el documento"""
        # No permitir envío directo, usar flujo de aprobación
        frappe.throw(_("Use el botón 'Enviar a Meta' para solicitar aprobación"))
    
    @log_whatsapp_template_event("INFO", "template_operation")
    @handle_whatsapp_template_errors("template_operation")
    @frappe.whitelist()
    def test_template(self):
        """Probar renderizado de plantilla"""
        try:
            logger.info("Iniciando prueba de plantilla", extra={
                'template_name': self.template_name,
                'template_type': self.template_type
            })
            
            # Obtener datos de prueba
            test_data = {}
            if self.test_data:
                try:
                    test_data = json.loads(self.test_data)
                except json.JSONDecodeError:
                    frappe.throw(_("Datos de prueba no son JSON válido"))
            
            # Usar datos por defecto si no hay datos de prueba
            if not test_data:
                test_data = {
                    'customer_name': 'Juan Pérez',
                    'invoice_number': 'INV-001',
                    'amount': '1,250.00',
                    'currency': 'COP',
                    'due_date': '25/12/2024',
                    'lead_name': 'María Gómez',
                    'company_name': 'KREO Colombia',
                    'support_email': 'soporte@kreo.com.co'
                }
            
            # Renderizar plantilla
            result = template_renderer.render_template(
                self.template_name,
                test_data,
                validate_required=False
            )
            
            # Actualizar vista previa
            self.content_preview = result
            self.save()
            
            logger.info("Prueba de plantilla completada exitosamente", extra={
                'template_name': self.template_name,
                'preview_length': len(result)
            })
            
            return {
                'success': True,
                'message': _('Plantilla probada exitosamente'),
                'preview': result,
                'length': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error probando plantilla {self.template_name}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }
    
    @frappe.whitelist()
    def render_preview(self):
        """Renderizar vista previa sin guardar"""
        try:
            test_data = {}
            if self.test_data:
                try:
                    test_data = json.loads(self.test_data)
                except json.JSONDecodeError:
                    pass
            
            if not test_data:
                test_data = {
                    'customer_name': 'Juan Pérez',
                    'invoice_number': 'INV-001',
                    'amount': '1,250.00',
                    'currency': 'COP',
                    'due_date': '25/12/2024',
                    'lead_name': 'María Gómez',
                    'company_name': 'KREO Colombia',
                    'support_email': 'soporte@kreo.com.co'
                }
            
            result = template_renderer.render_template(
                self.template_name,
                test_data,
                validate_required=False
            )
            
            return {
                'success': True,
                'preview': result,
                'length': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error renderizando vista previa: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    @frappe.whitelist()
    def clear_cache(self):
        """Limpiar cache de esta plantilla"""
        try:
            result = template_renderer.clear_template_cache(self.template_name)
            
            if result.get('success'):
                return {
                    'success': True,
                    'message': _('Cache limpiado exitosamente')
                }
            else:
                return {
                    'success': False,
                    'message': _('Error limpiando cache')
                }
                
        except Exception as e:
            logger.error(f"Error limpiando cache: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    @log_whatsapp_template_event("INFO", "template_operation")
    @handle_whatsapp_template_errors("template_operation")
    @frappe.whitelist()
    def submit_to_meta(self):
        """Enviar plantilla a Meta para aprobación"""
        try:
            logger.info("Iniciando envío de plantilla a Meta", extra={
                'template_name': self.template_name,
                'template_type': self.template_type,
                'current_status': self.status
            })
            
            # Validar que la plantilla esté completa
            if not self.content_html:
                frappe.throw(_("Complete el contenido HTML antes de enviar a Meta"))
            
            if not self.variables:
                frappe.throw(_("La plantilla debe tener variables definidas"))
            
            # Cambiar estado a pendiente de envío
            self.status = 'Pendiente de Envío'
            self.save()
            
            # Aquí iría la integración con Meta Business API
            # Por ahora, solo actualizamos el estado
            
            logger.info("Plantilla enviada a Meta exitosamente", extra={
                'template_name': self.template_name,
                'new_status': self.status
            })
            
            frappe.msgprint(
                _("Plantilla enviada a Meta para aprobación"),
                alert=True
            )
            
            return {
                'success': True,
                'message': _('Plantilla enviada a Meta')
            }
            
        except Exception as e:
            logger.error(f"Error enviando plantilla a Meta: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }
    
    @frappe.whitelist()
    def update_usage_stats(self):
        """Actualizar estadísticas de uso"""
        try:
            self.usage_count = (self.usage_count or 0) + 1
            self.last_used = datetime.now()
            self.save()
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas: {str(e)}")

@log_whatsapp_template_event("INFO", "template_operation")
@handle_whatsapp_template_errors("template_operation")
@frappe.whitelist()
def get_template_variables(template_name):
    """Obtener variables de una plantilla"""
    try:
        logger.info("Obteniendo variables de plantilla", extra={
            'template_name': template_name
        })
        
        result = template_renderer.get_template_variables(template_name)
        
        if result.get('success'):
            logger.info("Variables de plantilla obtenidas exitosamente", extra={
                'template_name': template_name,
                'variable_count': result.get('count', 0)
            })
            
            return {
                'success': True,
                'variables': result.get('variables', []),
                'count': result.get('count', 0)
            }
        else:
            logger.warning("No se pudieron obtener variables de plantilla", extra={
                'template_name': template_name,
                'error': result.get('error', 'Error desconocido')
            })
            
            return {
                'success': False,
                'message': result.get('error', 'Error desconocido')
            }
            
    except Exception as e:
        logger.error(f"Error obteniendo variables: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': str(e)
        }

@frappe.whitelist()
def create_template_from_file(template_name, template_type, file_path):
    """Crear plantilla desde archivo HTML"""
    try:
        # Validar parámetros
        if not template_name or not template_type or not file_path:
            frappe.throw(_("Todos los campos son requeridos"))
        
        validate_template_name(template_name)
        
        # Leer contenido del archivo
        import os
        if not os.path.exists(file_path):
            frappe.throw(_("Archivo no encontrado"))
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Crear documento
        template_doc = frappe.get_doc({
            'doctype': 'WhatsApp Template',
            'template_name': template_name,
            'template_type': template_type,
            'content_html': content,
            'status': 'En Revisión',
            'category': 'UTILITY',
            'language': 'es'
        })
        
        template_doc.insert()
        
        return {
            'success': True,
            'template_name': template_name,
            'message': _('Plantilla creada exitosamente')
        }
        
    except Exception as e:
        logger.error(f"Error creando plantilla desde archivo: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }

@frappe.whitelist()
def bulk_update_templates_status(template_names, new_status):
    """Actualizar estado de múltiples plantillas"""
    try:
        if not isinstance(template_names, list):
            template_names = [template_names]
        
        updated_count = 0
        for template_name in template_names:
            try:
                template_doc = frappe.get_doc('WhatsApp Template', template_name)
                template_doc.status = new_status
                template_doc.save()
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error actualizando {template_name}: {str(e)}")
        
        return {
            'success': True,
            'updated_count': updated_count,
            'total_count': len(template_names),
            'message': _(f'{updated_count} plantillas actualizadas')
        }
        
    except Exception as e:
        logger.error(f"Error en actualización masiva: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }