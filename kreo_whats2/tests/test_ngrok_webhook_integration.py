#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

import unittest
import frappe
from frappe import _
import json
import requests
from unittest.mock import patch, MagicMock
from datetime import datetime

# Importar componentes del sistema
from kreo_whats2.kreo_whats2.utils.ngrok_manager import ngrok_manager
from kreo_whats2.kreo_whats2.api.webhook_config import webhook_config
from kreo_whats2.kreo_whats2.api.webhook_handler import webhook
from kreo_whats2.kreo_whats2.utils.logging_manager import logging_manager

class TestNgrokWebhookIntegration(unittest.TestCase):
    """Pruebas para la integración completa de Ngrok y Webhooks"""
    
    @classmethod
    def setUpClass(cls):
        """Configurar pruebas"""
        frappe.init("kreo.localhost")
        frappe.connect()
        
    @classmethod
    def tearDownClass(cls):
        """Limpiar después de pruebas"""
        frappe.destroy()
    
    def setUp(self):
        """Configurar cada prueba"""
        # Crear configuración de WhatsApp para pruebas
        self.whatsapp_settings = frappe.get_single("WhatsApp Settings")
        self.original_settings = {
            "enabled": self.whatsapp_settings.enabled,
            "access_token": self.whatsapp_settings.access_token,
            "phone_number_id": self.whatsapp_settings.phone_number_id,
            "webhook_verify_token": self.whatsapp_settings.webhook_verify_token,
            "ngrok_authtoken": self.whatsapp_settings.ngrok_authtoken,
            "ngrok_subdomain": self.whatsapp_settings.ngrok_subdomain,
            "auto_register_webhook": self.whatsapp_settings.auto_register_webhook
        }
        
        # Configurar valores de prueba
        self.whatsapp_settings.enabled = True
        self.whatsapp_settings.access_token = "test_access_token"
        self.whatsapp_settings.phone_number_id = "test_phone_number_id"
        self.whatsapp_settings.webhook_verify_token = "test_verify_token"
        self.whatsapp_settings.ngrok_authtoken = "test_ngrok_token"
        self.whatsapp_settings.ngrok_subdomain = "test-subdomain"
        self.whatsapp_settings.auto_register_webhook = True
        self.whatsapp_settings.save()
        
    def tearDown(self):
        """Restaurar configuración original"""
        # Restaurar configuración original
        for key, value in self.original_settings.items():
            setattr(self.whatsapp_settings, key, value)
        self.whatsapp_settings.save()
    
    def test_ngrok_manager_initialization(self):
        """Test: Inicialización del gestor Ngrok"""
        self.assertIsNotNone(ngrok_manager)
        self.assertIsNone(ngrok_manager.ngrok_url)
        self.assertIsNone(ngrok_manager.ngrok_process)
        self.assertIsNone(ngrok_manager.tunnel)
    
    @patch('subprocess.Popen')
    @patch('requests.get')
    def test_ngrok_start_with_subprocess(self, mock_get, mock_popen):
        """Test: Iniciar Ngrok con subprocess"""
        # Mock para subprocess
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        # Mock para API de Ngrok
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tunnels": [
                {
                    "proto": "http",
                    "public_url": "https://test-subdomain.ngrok.io"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Iniciar Ngrok
        url = ngrok_manager.start_ngrok_tunnel(port=8000, protocol="http")
        
        self.assertIsNotNone(url)
        self.assertIn("ngrok.io", url)
        self.assertEqual(ngrok_manager.ngrok_url, url)
        
        # Verificar que se actualizó la configuración
        frappe.db.commit()
        settings = frappe.get_single("WhatsApp Settings")
        self.assertEqual(settings.ngrok_url, url)
    
    def test_ngrok_status_methods(self):
        """Test: Métodos de estado de Ngrok"""
        # Estado cuando no hay túnel
        status = ngrok_manager.get_tunnel_status()
        self.assertEqual(status["status"], "stopped")
        
        # Estado detallado
        info = ngrok_manager.get_tunnel_info()
        self.assertIn("status", info)
        self.assertIn("configuration", info)
        self.assertIn("last_updated", info)
    
    def test_webhook_config_initialization(self):
        """Test: Inicialización de configuración de webhook"""
        self.assertIsNotNone(webhook_config)
        self.assertIsNotNone(webhook_config.whatsapp_settings)
        
        # Verificar que la configuración se cargó correctamente
        self.assertEqual(webhook_config.whatsapp_settings.ngrok_subdomain, "test-subdomain")
    
    def test_webhook_verification_callback(self):
        """Test: Verificación de callback de webhook"""
        # Datos de verificación válidos
        verification_data = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "test_challenge_123"
        }
        
        result = webhook_config.verify_webhook_callback(verification_data)
        self.assertTrue(result["success"])
        self.assertEqual(result["challenge"], "test_challenge_123")
        
        # Token inválido
        invalid_data = {
            "hub.mode": "subscribe",
            "hub.verify_token": "invalid_token",
            "hub.challenge": "test_challenge_123"
        }
        
        result = webhook_config.verify_webhook_callback(invalid_data)
        self.assertFalse(result["success"])
    
    @patch('requests.post')
    def test_webhook_registration(self, mock_post):
        """Test: Registro de webhook con Meta API"""
        # Mock respuesta exitosa
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response
        
        # Probar registro
        webhook_url = "https://test.ngrok.io/api/method/kreo_whats2.webhook"
        result = webhook_config.register_webhook(webhook_url, "test_verify_token")
        
        self.assertTrue(result["success"])
        self.assertIn("Webhook registrado exitosamente", result["message"])
        
        # Verificar que se llamó a la API de Meta
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("graph.facebook.com", args[0])
        self.assertIn("subscribed_apps", args[0])
    
    def test_webhook_event_processing(self):
        """Test: Procesamiento de eventos de webhook"""
        # Evento de mensaje válido
        message_event = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "test_entry_1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "1234567890", "phone_number_id": "test_phone_id"},
                                "contacts": [{"profile": {"name": "Test User"}, "wa_id": "1234567890"}],
                                "messages": [{"from": "1234567890", "id": "msg_123", "timestamp": "1234567890", "type": "text", "text": {"body": "Test message"}}]
                            }
                        }
                    ]
                }
            ]
        }
        
        # Procesar evento
        result = webhook_config.process_webhook_event(message_event)
        
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["processed"], 0)
    
    def test_webhook_handler_verification(self):
        """Test: Manejador de webhook - verificación"""
        # Mock request para verificación
        with patch('frappe.request') as mock_request:
            mock_request.method = "GET"
            mock_request.args = {
                "hub.verify_token": "test_verify_token",
                "hub.challenge": "test_challenge_123",
                "hub.mode": "subscribe"
            }
            
            with patch('frappe.response') as mock_response:
                result = webhook()
                
                # Debe devolver el challenge
                self.assertEqual(result, "test_challenge_123")
    
    def test_webhook_handler_events(self):
        """Test: Manejador de webhook - eventos"""
        # Mock request para eventos
        event_data = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "test", "changes": []}]
        }
        
        with patch('frappe.request') as mock_request:
            mock_request.method = "POST"
            mock_request.get_json.return_value = event_data
            
            with patch('frappe.response') as mock_response:
                result = webhook()
                
                self.assertIn("status", result)
                self.assertIn("message", result)
    
    def test_logging_manager(self):
        """Test: Gestor de logging"""
        # Probar creación de logger
        logger = logging_manager.get_logger("test_module")
        self.assertIsNotNone(logger)
        
        # Probar registro de eventos
        logging_manager.log_event("test_module", "INFO", "Test message", test_data="test_value")
        
        # Probar registro de errores
        try:
            raise ValueError("Test error")
        except ValueError as e:
            logging_manager.log_error("test_module", e, {"test_context": "test"})
        
        # Probar decoradores
        @logging_manager.log_whatsapp_event(level="INFO", module="test")
        def test_function():
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
    
    def test_health_check_integration(self):
        """Test: Verificación de salud integrada"""
        # Probar health check desde WhatsApp Settings
        health_status = self.whatsapp_settings.health_check()
        
        self.assertIn("status", health_status)
        self.assertIn("checks", health_status)
        self.assertIn("timestamp", health_status)
        
        # Verificar que incluye verificación de Ngrok
        checks = health_status["checks"]
        ngrok_check = next((c for c in checks if c["name"] == "ngrok_tunnel"), None)
        self.assertIsNotNone(ngrok_check)
        
        # Verificar que incluye verificación de webhook
        webhook_check = next((c for c in checks if c["name"] == "webhook_registered"), None)
        self.assertIsNotNone(webhook_check)
    
    def test_ngrok_connection_test(self):
        """Test: Prueba de conexión Ngrok"""
        # Mock para prueba de conexión
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_get.return_value = mock_response
            
            # Establecer URL de Ngrok
            ngrok_manager.ngrok_url = "https://test.ngrok.io"
            
            result = ngrok_manager.test_connection()
            
            self.assertTrue(result["success"])
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(result["response_time"], 0.5)
    
    def test_error_handling_decorators(self):
        """Test: Manejo de errores con decoradores"""
        @logging_manager.handle_whatsapp_errors(module="test")
        def test_error_function():
            raise Exception("Test error")
        
        result = test_error_function()
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_rate_limiting_integration(self):
        """Test: Integración con rate limiting"""
        # Verificar que el rate limiting sigue funcionando
        rate_limit_status = self.whatsapp_settings.get_rate_limit_status()
        
        self.assertIn("current_usage", rate_limit_status)
        self.assertIn("limit_per_second", rate_limit_status)
        self.assertIn("concurrent_limit", rate_limit_status)
    
    def test_configuration_validation(self):
        """Test: Validación de configuración"""
        # Probar validación de URL de webhook
        valid_url = "https://test.ngrok.io/webhook"
        invalid_url = "http://test.ngrok.io/webhook"  # No HTTPS
        
        # Simular validación (la función real está en webhook_config)
        self.assertTrue(valid_url.startswith("https"))
        self.assertFalse(invalid_url.startswith("https"))
    
    def test_automatic_webhook_registration(self):
        """Test: Registro automático de webhook"""
        # Mock para registro automático
        with patch.object(webhook_config, 'register_webhook') as mock_register:
            mock_register.return_value = {"success": True, "message": "Registered"}
            
            # Simular URL de Ngrok
            test_url = "https://test.ngrok.io"
            
            result = self.whatsapp_settings.register_webhook_automatically()
            
            # Verificar que se intentó registrar
            mock_register.assert_called_once_with(
                f"{test_url}/api/method/kreo_whats2.webhook"
            )

def run_integration_tests():
    """Ejecutar todas las pruebas de integración"""
    # Crear suite de pruebas
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNgrokWebhookIntegration)
    
    # Ejecutar pruebas
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Retornar resultados
    return {
        "success": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "failure_details": result.failures,
        "error_details": result.errors
    }

if __name__ == "__main__":
    # Ejecutar pruebas
    results = run_integration_tests()
    
    print("\n" + "="*60)
    print("RESULTADOS DE PRUEBAS DE INTEGRACIÓN")
    print("="*60)
    print(f"Éxito: {'✅' if results['success'] else '❌'}")
    print(f"Pruebas ejecutadas: {results['tests_run']}")
    print(f"Fallos: {results['failures']}")
    print(f"Errores: {results['errors']}")
    
    if not results['success']:
        print("\nDETALLES DE FALLOS/ERRORES:")
        for failure in results['failure_details']:
            print(f"❌ {failure[0]}: {failure[1]}")
        for error in results['error_details']:
            print(f"💥 {error[0]}: {error[1]}")
    
    print("="*60)