# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import unittest
import json
from datetime import datetime
from kreo_whats2.kreo_whats2.api.template_renderer import template_renderer, TemplateRendererError
from kreo_whats2.kreo_whats2.api.queue_processor import queue_processor
from kreo_whats2.kreo_whats2.doctype.whatsapp_template.whatsapp_template import WhatsAppTemplate

class TestTemplateIntegration(unittest.TestCase):
    """Pruebas de integración del sistema de plantillas WhatsApp"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        self.test_data = {
            'customer_name': 'Juan Pérez',
            'invoice_number': 'INV-001',
            'amount': '1,250.00',
            'currency': 'COP',
            'due_date': '25/12/2024',
            'lead_name': 'María Gómez',
            'company_name': 'KREO Colombia',
            'support_email': 'soporte@kreo.com.co'
        }
    
    def test_template_renderer_basic_functionality(self):
        """Test: Funcionalidad básica del renderizador de plantillas"""
        try:
            # Probar renderizado de factura
            result = template_renderer.render_template(
                'factura_emitida',
                self.test_data
            )
            
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)
            self.assertIn('Juan Pérez', result)
            self.assertIn('INV-001', result)
            self.assertIn('1,250.00', result)
            
            # Probar renderizado de recordatorio
            result = template_renderer.render_template(
                'recordatorio_pago',
                self.test_data
            )
            
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)
            self.assertIn('Juan Pérez', result)
            
            # Probar renderizado de bienvenida
            result = template_renderer.render_template(
                'bienvenida_lead',
                self.test_data
            )
            
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)
            self.assertIn('María Gómez', result)
            
        except Exception as e:
            self.fail(f"Error en renderizado básico: {str(e)}")
    
    def test_template_renderer_cache_functionality(self):
        """Test: Funcionalidad de cache del renderizador"""
        try:
            # Renderizar primera vez (debe generar cache)
            result1 = template_renderer.render_template(
                'factura_emitida',
                self.test_data
            )
            
            # Renderizar segunda vez (debe usar cache)
            result2 = template_renderer.render_template(
                'factura_emitida',
                self.test_data
            )
            
            # Los resultados deben ser idénticos
            self.assertEqual(result1, result2)
            
        except Exception as e:
            self.fail(f"Error en cache: {str(e)}")
    
    def test_template_renderer_security_validation(self):
        """Test: Validación de seguridad del renderizador"""
        try:
            # Probar con contenido potencialmente peligroso
            malicious_data = {
                'customer_name': '<script>alert("xss")</script>',
                'invoice_number': 'INV-001',
                'amount': '1000',
                'currency': 'COP'
            }
            
            result = template_renderer.render_template(
                'factura_emitida',
                malicious_data
            )
            
            # El script debe estar sanitizado
            self.assertNotIn('<script>', result)
            self.assertNotIn('alert', result)
            
        except Exception as e:
            self.fail(f"Error en validación de seguridad: {str(e)}")
    
    def test_template_renderer_error_handling(self):
        """Test: Manejo de errores del renderizador"""
        try:
            # Probar con plantilla inexistente
            with self.assertRaises(TemplateRendererError):
                template_renderer.render_template('plantilla_inexistente', {})
            
            # Probar con datos inválidos
            with self.assertRaises(TemplateRendererError):
                template_renderer.render_template('factura_emitida', 'datos_invalidos')
                
        except Exception as e:
            self.fail(f"Error en manejo de errores: {str(e)}")
    
    def test_redis_queue_integration(self):
        """Test: Integración con Redis Queue"""
        try:
            # Verificar conexión a Redis
            self.assertIsNotNone(queue_processor.redis_client)
            
            # Probar encolado de mensaje
            test_message = {
                'message_id': 'test_001',
                'recipient_phone': '+573001234567',
                'content': 'Mensaje de prueba',
                'template_name': 'factura_emitida',
                'template_data': json.dumps(self.test_data),
                'priority': 'normal'
            }
            
            result = queue_processor.redis_client.lpush(
                'test_whatsapp_queue',
                json.dumps(test_message)
            )
            
            self.assertIsNotNone(result)
            
            # Limpiar cola de prueba
            queue_processor.redis_client.delete('test_whatsapp_queue')
            
        except Exception as e:
            self.fail(f"Error en integración con Redis: {str(e)}")
    
    def test_template_variables_extraction(self):
        """Test: Extracción de variables de plantillas"""
        try:
            # Probar extracción de variables
            result = template_renderer.get_template_variables('factura_emitida')
            
            self.assertTrue(result['success'])
            self.assertIsInstance(result['variables'], list)
            self.assertGreater(len(result['variables']), 0)
            
            # Verificar que ciertas variables estén presentes
            variables = result['variables']
            self.assertIn('customer_name', variables)
            self.assertIn('invoice_number', variables)
            self.assertIn('amount', variables)
            
        except Exception as e:
            self.fail(f"Error en extracción de variables: {str(e)}")
    
    def test_template_cache_clearing(self):
        """Test: Limpieza de cache de plantillas"""
        try:
            # Renderizar y cachear
            template_renderer.render_template('factura_emitida', self.test_data)
            
            # Limpiar cache específica
            result = template_renderer.clear_template_cache('factura_emitida')
            self.assertTrue(result['success'])
            
            # Limpiar todo el cache
            result = template_renderer.clear_template_cache()
            self.assertTrue(result['success'])
            
        except Exception as e:
            self.fail(f"Error en limpieza de cache: {str(e)}")
    
    def test_template_testing_functionality(self):
        """Test: Funcionalidad de prueba de plantillas"""
        try:
            # Probar función de test
            result = template_renderer.test_template('factura_emitida', self.test_data)
            
            self.assertTrue(result['success'])
            self.assertIsInstance(result['content'], str)
            self.assertGreater(len(result['content']), 0)
            self.assertIn('Juan Pérez', result['content'])
            
        except Exception as e:
            self.fail(f"Error en función de prueba: {str(e)}")
    
    def test_whatsapp_template_doctype(self):
        """Test: Funcionalidad del DocType WhatsApp Template"""
        try:
            # Crear documento de prueba
            template_doc = frappe.get_doc({
                'doctype': 'WhatsApp Template',
                'template_name': 'test_template',
                'template_type': 'General',
                'content_html': '<h1>Test {{test_var}}</h1>',
                'status': 'En Revisión',
                'category': 'UTILITY',
                'language': 'es'
            })
            
            template_doc.insert()
            
            # Verificar que se creó correctamente
            self.assertEqual(template_doc.template_name, 'test_template')
            self.assertEqual(template_doc.template_type, 'General')
            
            # Probar extracción de variables
            variables = template_doc.variables
            self.assertEqual(len(variables), 1)
            self.assertEqual(variables[0].variable_name, 'test_var')
            
            # Limpiar
            template_doc.delete()
            
        except Exception as e:
            self.fail(f"Error en DocType WhatsApp Template: {str(e)}")
    
    def test_template_automation_hooks(self):
        """Test: Funcionalidad de los hooks de automatización"""
        try:
            # Importar hooks
            from kreo_whats2.kreo_whats2.hooks.template_automation_hooks import TemplateAutomationHooks
            
            # Verificar que las funciones existen
            self.assertTrue(hasattr(TemplateAutomationHooks, 'send_invoice_template'))
            self.assertTrue(hasattr(TemplateAutomationHooks, 'send_payment_reminder_template'))
            self.assertTrue(hasattr(TemplateAutomationHooks, 'send_lead_welcome_template'))
            
        except Exception as e:
            self.fail(f"Error en hooks de automatización: {str(e)}")

def run_template_integration_tests():
    """Ejecutar todas las pruebas de integración"""
    try:
        # Crear suite de pruebas
        suite = unittest.TestLoader().loadTestsFromTestCase(TestTemplateIntegration)
        
        # Ejecutar pruebas
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Retornar resultados
        return {
            'success': result.wasSuccessful(),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'failure_details': result.failures,
            'error_details': result.errors
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'tests_run': 0,
            'failures': 0,
            'errors': 1
        }

@frappe.whitelist()
def test_template_system():
    """Endpoint para probar el sistema de plantillas"""
    try:
        results = run_template_integration_tests()
        
        if results['success']:
            frappe.msgprint(
                _("✅ Todas las pruebas de plantillas pasaron exitosamente"),
                alert=True
            )
        else:
            frappe.msgprint(
                _("❌ Algunas pruebas de plantillas fallaron"),
                alert=True
            )
        
        return results
        
    except Exception as e:
        frappe.log_error(f"Error ejecutando pruebas de plantillas: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    # Ejecutar pruebas si se llama directamente
    results = run_template_integration_tests()
    print(f"Resultados: {results}")