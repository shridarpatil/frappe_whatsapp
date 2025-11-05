# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import os
import json
import logging
import hashlib
import time
from datetime import datetime, timedelta
from jinja2 import Template, Environment, select_autoescape, TemplateSyntaxError, UndefinedError
from functools import wraps
import redis
import bleach

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event,
        handle_whatsapp_errors, get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
    logger = get_logger("template_renderer")
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible")

# Configuración de logging
logger = logging.getLogger(__name__)

class TemplateRendererError(Exception):
    """Excepción personalizada para errores del renderizador de plantillas"""
    pass

class TemplateCache:
    """Gestión de cache para plantillas renderizadas"""
    
    def __init__(self, redis_url="redis://redis-cache:6379/2"):
        self.redis_client = None
        self._connect_redis(redis_url)
        self.cache_ttl = 3600  # 1 hora de TTL
    
    def _connect_redis(self, redis_url):
        """Conectar a Redis para cache"""
        try:
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            logger.info("Conectado a Redis Cache para plantillas")
        except Exception as e:
            logger.error(f"Error conectando a Redis Cache: {str(e)}")
            self.redis_client = None
    
    def _generate_cache_key(self, template_name, template_data):
        """Generar clave única para cache basada en plantilla y datos"""
        cache_input = f"{template_name}:{json.dumps(template_data, sort_keys=True)}"
        return f"whatsapp_template:{hashlib.md5(cache_input.encode()).hexdigest()}"
    
    def get_cached_template(self, template_name, template_data):
        """Obtener plantilla desde cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(template_name, template_data)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                cache_data = json.loads(cached_data)
                # Verificar si el cache aún es válido
                if datetime.now().timestamp() < cache_data.get('expires_at', 0):
                    logger.debug(f"Plantilla {template_name} obtenida desde cache")
                    return cache_data.get('content')
                
                # Eliminar cache expirado
                self.redis_client.delete(cache_key)
                
        except Exception as e:
            logger.error(f"Error obteniendo cache de plantilla: {str(e)}")
        
        return None
    
    def cache_template(self, template_name, template_data, content):
        """Almacenar plantilla en cache"""
        if not self.redis_client:
            return
        
        try:
            cache_key = self._generate_cache_key(template_name, template_data)
            cache_data = {
                'content': content,
                'expires_at': datetime.now().timestamp() + self.cache_ttl
            }
            
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(cache_data)
            )
            logger.debug(f"Plantilla {template_name} almacenada en cache")
            
        except Exception as e:
            logger.error(f"Error almacenando cache de plantilla: {str(e)}")

class TemplateSecurityValidator:
    """Validador de seguridad para plantillas"""
    
    def __init__(self):
        # Configuración de bleach para sanitización HTML
        self.allowed_tags = [
            'p', 'div', 'span', 'strong', 'em', 'b', 'i', 'u', 'br', 'hr',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a',
            'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'blockquote',
            'code', 'pre'
        ]
        
        self.allowed_attributes = {
            '*': ['class', 'id', 'style'],
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height'],
            'table': ['border', 'cellpadding', 'cellspacing'],
        }
    
    def sanitize_html(self, html_content):
        """Sanitizar HTML para prevenir XSS"""
        try:
            sanitized = bleach.clean(
                html_content,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                strip=True
            )
            return sanitized
        except Exception as e:
            logger.error(f"Error sanitizando HTML: {str(e)}")
            return html_content
    
    def validate_template_content(self, template_content):
        """Validar contenido de plantilla para cumplir políticas de Meta"""
        violations = []
        
        # Verificar longitud máxima
        if len(template_content) > 1024:
            violations.append("El contenido excede el límite de 1024 caracteres")
        
        # Verificar contenido inapropiado
        prohibited_words = [
            'pornografía', 'drogas', 'violencia', 'armas', 'discriminación',
            'spam', 'phishing', 'fraude', 'estafa'
        ]
        
        content_lower = template_content.lower()
        for word in prohibited_words:
            if word in content_lower:
                violations.append(f"Contenido prohibido detectado: {word}")
        
        # Verificar estructura HTML básica
        if '<script' in template_content.lower():
            violations.append("Etiquetas <script> no permitidas")
        
        if 'javascript:' in template_content.lower():
            violations.append("Event handlers JavaScript no permitidos")
        
        return violations

def log_template_event(level="INFO", module="template_renderer"):
    """Decorador para logging de eventos de plantillas"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            
            try:
                logger.log(
                    getattr(logging, level.upper(), logging.INFO),
                    f"Iniciando {func.__name__}"
                )
                
                result = func(*args, **kwargs)
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Template {func.__name__} completado en {duration:.3f}s")
                
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"Error en {func.__name__} después de {duration:.3f}s: {str(e)}")
                raise
                
        return wrapper
    return decorator

class TemplateRenderer:
    """Motor de renderizado de plantillas HTML para WhatsApp Business API"""
    
    def __init__(self):
        self.template_dir = frappe.get_app_path('kreo_whats2', 'templates')
        self.jinja_env = self._setup_jinja_environment()
        self.template_cache = TemplateCache()
        self.security_validator = TemplateSecurityValidator()
        self._setup_logging()
    
    def _setup_logging(self):
        """Configurar logging detallado"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if whatsapp_settings.enable_detailed_logging:
                log_level = getattr(logging, whatsapp_settings.log_level.upper(), logging.INFO)
                logger.setLevel(log_level)
                
                # Configurar handler para archivo
                log_file = f"{whatsapp_settings.log_file_path or 'logs/whatsapp'}/template_renderer.log"
                import os
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(log_level)
                
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
                )
                file_handler.setFormatter(formatter)
                
                logger.addHandler(file_handler)
                
        except Exception as e:
            logger.error(f"Error configurando logging: {str(e)}")
    
    def _setup_jinja_environment(self):
        """Configurar entorno Jinja2 seguro"""
        return Environment(
            autoescape=select_autoescape(['html', 'xml']),
            enable_async=False
        )
    
    def _load_template_file(self, template_name):
        """Cargar archivo de plantilla desde disco"""
        template_path = os.path.join(self.template_dir, f"{template_name}.html")
        
        if not os.path.exists(template_path):
            raise TemplateRendererError(f"Plantilla no encontrada: {template_name}")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise TemplateRendererError(f"Error leyendo plantilla {template_name}: {str(e)}")
    
    def _validate_required_variables(self, template_content, required_vars):
        """Validar que las variables requeridas estén presentes"""
        missing_vars = []
        
        for var in required_vars:
            if f"{{{{ {var} }}}}" not in template_content and f"{{% {var} %}}" not in template_content:
                missing_vars.append(var)
        
        return missing_vars
    
    def _convert_html_to_whatsapp_format(self, html_content):
        """Convertir HTML a formato compatible con WhatsApp"""
        # WhatsApp Business API espera texto plano con ciertos formatos
        # Convertimos el HTML a un formato compatible
        
        # Reemplazar etiquetas HTML con formatos de WhatsApp
        whatsapp_content = html_content
        
        # Convertir negritas
        whatsapp_content = whatsapp_content.replace('<strong>', '*').replace('</strong>', '*')
        whatsapp_content = whatsapp_content.replace('<b>', '*').replace('</b>', '*')
        
        # Convertir cursivas
        whatsapp_content = whatsapp_content.replace('<em>', '_').replace('</em>', '_')
        whatsapp_content = whatsapp_content.replace('<i>', '_').replace('</i>', '_')
        
        # Convertir encabezados
        whatsapp_content = whatsapp_content.replace('<h1>', '*').replace('</h1>', '*\n')
        whatsapp_content = whatsapp_content.replace('<h2>', '*').replace('</h2>', '*\n')
        whatsapp_content = whatsapp_content.replace('<h3>', '*').replace('</h3>', '*\n')
        
        # Convertir saltos de línea
        whatsapp_content = whatsapp_content.replace('<br>', '\n').replace('<br/>', '\n')
        whatsapp_content = whatsapp_content.replace('<br />', '\n')
        
        # Convertir párrafos
        whatsapp_content = whatsapp_content.replace('</p><p>', '\n\n')
        whatsapp_content = whatsapp_content.replace('<p>', '').replace('</p>', '\n')
        
        # Eliminar otras etiquetas HTML
        import re
        whatsapp_content = re.sub(r'<[^>]+>', '', whatsapp_content)
        
        # Limpiar espacios extra
        whatsapp_content = re.sub(r'\n\s*\n', '\n\n', whatsapp_content)
        whatsapp_content = whatsapp_content.strip()
        
        return whatsapp_content
    
    @log_whatsapp_event("template_rendering")
    @handle_whatsapp_errors("template_renderer")
    def render_template(self, template_name, template_data=None, validate_required=True):
        """Renderizar plantilla con datos dinámicos"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "template_rendering",
                    metadata={
                        "operation": "render_template",
                        "template_name": template_name,
                        "has_template_data": bool(template_data),
                        "validate_required": validate_required
                    }
                )
            
            # Validar parámetros
            if not template_name:
                raise TemplateRendererError("Nombre de plantilla requerido")
            
            if template_data is None:
                template_data = {}
            
            # Convertir datos a diccionario si es JSON
            if isinstance(template_data, str):
                try:
                    template_data = json.loads(template_data)
                except json.JSONDecodeError:
                    # Registrar error con logging avanzado
                    if ADVANCED_LOGGING_AVAILABLE:
                        logging_manager.log_event("template_renderer", "invalid_template_data", {
                            "status": "error",
                            "error_type": "invalid_json",
                            "template_name": template_name
                        })
                        
                        logging_manager.end_operation_context(
                            correlation_id, "error",
                            error_details={
                                "error_type": "invalid_json",
                                "template_name": template_name,
                                "message": "Datos de plantilla no son JSON válido"
                            }
                        )
                    
                    raise TemplateRendererError("Datos de plantilla no son JSON válido")
            
            # Verificar cache primero
            cached_content = self.template_cache.get_cached_template(template_name, template_data)
            if cached_content:
                # Registrar hit de cache con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    response_time = (time.time() - start_time) * 1000
                    logging_manager.log_event("template_renderer", "template_cache_hit", {
                        "status": "success",
                        "template_name": template_name,
                        "cache_used": True
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "template_cache_hits": 1
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
                
                return cached_content
            
            # Cargar plantilla
            template_content = self._load_template_file(template_name)
            
            # Validar variables requeridas
            if validate_required:
                required_vars = self._get_required_variables(template_name)
                missing_vars = self._validate_required_variables(template_content, required_vars)
                
                if missing_vars:
                    # Registrar advertencia con logging avanzado
                    if ADVANCED_LOGGING_AVAILABLE:
                        logging_manager.log_event("template_renderer", "missing_template_variables", {
                            "status": "warning",
                            "template_name": template_name,
                            "missing_variables": missing_vars,
                            "total_required": len(required_vars)
                        })
                        
                        logging_manager.end_operation_context(
                            correlation_id, "warning",
                            warning_details={
                                "missing_variables": missing_vars,
                                "template_name": template_name
                            }
                        )
                    
                    logger.warning(f"Variables requeridas faltantes en {template_name}: {missing_vars}")
                    # No lanzar error, solo advertir y continuar
            
            # Renderizar con Jinja2
            try:
                template = self.jinja_env.from_string(template_content)
                rendered_html = template.render(**template_data)
            except (TemplateSyntaxError, UndefinedError) as e:
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("template_renderer", "template_syntax_error", {
                        "status": "error",
                        "error_type": "syntax_error",
                        "template_name": template_name,
                        "error_message": str(e)
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "syntax_error",
                            "template_name": template_name,
                            "error_message": str(e)
                        }
                    )
                
                raise TemplateRendererError(f"Error de sintaxis en plantilla {template_name}: {str(e)}")
            
            # Validar seguridad
            security_violations = self.security_validator.validate_template_content(rendered_html)
            if security_violations:
                # Registrar advertencia de seguridad con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("template_renderer", "security_violations_detected", {
                        "status": "warning",
                        "template_name": template_name,
                        "violations_count": len(security_violations),
                        "violations": security_violations
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "warning",
                        warning_details={
                            "violations_count": len(security_violations),
                            "violations": security_violations,
                            "template_name": template_name
                        }
                    )
                
                logger.warning(f"Violaciones de seguridad en plantilla {template_name}: {security_violations}")
                # No lanzar error, solo advertir y sanitizar
            
            # Sanitizar HTML
            sanitized_html = self.security_validator.sanitize_html(rendered_html)
            
            # Convertir a formato WhatsApp
            whatsapp_content = self._convert_html_to_whatsapp_format(sanitized_html)
            
            # Validar longitud final
            if len(whatsapp_content) > 1024:
                # Registrar advertencia de longitud con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("template_renderer", "template_content_too_long", {
                        "status": "warning",
                        "template_name": template_name,
                        "content_length": len(whatsapp_content),
                        "truncated": True
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "warning",
                        warning_details={
                            "content_length": len(whatsapp_content),
                            "template_name": template_name,
                            "truncated": True
                        }
                    )
                
                logger.warning(f"Contenido de plantilla {template_name} excede 1024 caracteres: {len(whatsapp_content)}")
                whatsapp_content = whatsapp_content[:1020] + "..."
            
            # Almacenar en cache
            self.template_cache.cache_template(template_name, template_data, whatsapp_content)
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                response_time = (time.time() - start_time) * 1000
                logging_manager.log_event("template_renderer", "template_rendered_success", {
                    "status": "success",
                    "template_name": template_name,
                    "content_length": len(whatsapp_content),
                    "cache_used": False,
                    "validation_passed": True
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "templates_rendered": 1,
                        "template_cache_misses": 1
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
            
            logger.info(f"Plantilla {template_name} renderizada exitosamente")
            return whatsapp_content
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("template_renderer", e, {
                    "operation": "render_template",
                    "correlation_id": correlation_id,
                    "template_name": template_name
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e),
                            "template_name": template_name
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error renderizando plantilla {template_name}: {str(e)}")
            raise TemplateRendererError(f"Error renderizando plantilla {template_name}: {str(e)}")
    
    def _get_required_variables(self, template_name):
        """Obtener variables requeridas para cada tipo de plantilla"""
        required_vars_map = {
            'factura_emitida': ['customer_name', 'invoice_number', 'amount', 'currency'],
            'recordatorio_pago': ['customer_name', 'invoice_number', 'amount', 'currency', 'due_date'],
            'bienvenida_lead': ['lead_name', 'company_name']
        }
        
        return required_vars_map.get(template_name, [])
    
    @log_whatsapp_event("template_testing")
    @handle_whatsapp_errors("template_renderer")
    def test_template(self, template_name, test_data=None):
        """Probar renderizado de plantilla con datos de prueba"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "template_testing",
                    metadata={
                        "operation": "test_template",
                        "template_name": template_name,
                        "has_custom_data": bool(test_data)
                    }
                )
            
            if test_data is None:
                # Datos de prueba por defecto
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
            
            result = self.render_template(template_name, test_data, validate_required=False)
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                response_time = (time.time() - start_time) * 1000
                logging_manager.log_event("template_renderer", "template_test_success", {
                    "status": "success",
                    "template_name": template_name,
                    "content_length": len(result),
                    "test_data_used": bool(test_data)
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "template_tests": 1
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
            
            return {
                'success': True,
                'content': result,
                'length': len(result),
                'test_data': test_data
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("template_renderer", e, {
                    "operation": "test_template",
                    "correlation_id": correlation_id,
                    "template_name": template_name
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e),
                            "template_name": template_name
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            return {
                'success': False,
                'error': str(e),
                'template_name': template_name
            }
    
    def get_template_variables(self, template_name):
        """Obtener lista de variables disponibles en una plantilla"""
        try:
            template_content = self._load_template_file(template_name)
            
            # Extraer variables de Jinja2
            import re
            variable_pattern = r'\{\{\s*(\w+)\s*\}\}'
            variables = list(set(re.findall(variable_pattern, template_content)))
            
            # Extraer variables de bloques if
            if_pattern = r'\{\%\s*if\s+(\w+)\s*\%\}'
            if_variables = list(set(re.findall(if_pattern, template_content)))
            
            all_variables = list(set(variables + if_variables))
            
            return {
                'success': True,
                'variables': all_variables,
                'count': len(all_variables)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @log_whatsapp_event("template_cache_clearing")
    @handle_whatsapp_errors("template_renderer")
    def clear_template_cache(self, template_name=None):
        """Limpiar cache de plantillas"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "template_cache_clearing",
                    metadata={
                        "operation": "clear_template_cache",
                        "template_name": template_name,
                        "clear_all": template_name is None
                    }
                )
            
            if self.template_cache.redis_client:
                if template_name:
                    # Limpiar cache específica de una plantilla
                    pattern = f"whatsapp_template:*{template_name}*"
                    keys = self.template_cache.redis_client.keys(pattern)
                    if keys:
                        self.template_cache.redis_client.delete(*keys)
                    
                    # Registrar operación exitosa con logging avanzado
                    if ADVANCED_LOGGING_AVAILABLE:
                        response_time = (time.time() - start_time) * 1000
                        logging_manager.log_event("template_renderer", "template_cache_cleared", {
                            "status": "success",
                            "template_name": template_name,
                            "keys_deleted": len(keys) if keys else 0,
                            "clear_all": False
                        }, performance_metrics={
                            "response_time_ms": response_time
                        })
                        
                        logging_manager.end_operation_context(
                            correlation_id, "success",
                            business_metrics={
                                "cache_clears": 1,
                                "keys_deleted": len(keys) if keys else 0
                            },
                            performance_metrics={
                                "response_time_ms": response_time
                            }
                        )
                    
                    logger.info(f"Cache limpiada para plantilla: {template_name}")
                else:
                    # Limpiar todo el cache
                    self.template_cache.redis_client.flushdb()
                    
                    # Registrar operación exitosa con logging avanzado
                    if ADVANCED_LOGGING_AVAILABLE:
                        response_time = (time.time() - start_time) * 1000
                        logging_manager.log_event("template_renderer", "all_template_cache_cleared", {
                            "status": "success",
                            "clear_all": True
                        }, performance_metrics={
                            "response_time_ms": response_time
                        })
                        
                        logging_manager.end_operation_context(
                            correlation_id, "success",
                            business_metrics={
                                "cache_clears": 1,
                                "all_cache_cleared": True
                            },
                            performance_metrics={
                                "response_time_ms": response_time
                            }
                        )
                    
                    logger.info("Cache de plantillas completamente limpiado")
                
                return {'success': True}
            else:
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("template_renderer", "redis_unavailable_for_cache_clear", {
                        "status": "error",
                        "error_type": "redis_unavailable",
                        "template_name": template_name
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "redis_unavailable",
                            "message": "Redis no disponible para limpieza de cache"
                        }
                    )
                
                return {'success': False, 'error': 'Redis no disponible'}
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("template_renderer", e, {
                    "operation": "clear_template_cache",
                    "correlation_id": correlation_id,
                    "template_name": template_name
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e),
                            "template_name": template_name
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error limpiando cache: {str(e)}")
            return {'success': False, 'error': str(e)}

# Instancia global del renderizador
template_renderer = TemplateRenderer()