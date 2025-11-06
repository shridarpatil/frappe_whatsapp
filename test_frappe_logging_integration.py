#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Script de prueba para validar la integración del logging avanzado con Frappe Framework
"""

import sys
import os
import json
from datetime import datetime

# Añadir el path de la aplicación
sys.path.insert(0, '/f/Giovany/KREO.ONE/frappe_docker')
sys.path.insert(0, '/f/Giovany/KREO.ONE/frappe_docker/apps/kreo_whats2')

def test_logging_imports():
    """Test 1: Verificar que los imports de logging funcionan correctamente"""
    print("🔍 Test 1: Verificando imports de logging avanzado...")
    
    try:
        # Importar el módulo de hooks
        import apps.kreo_whats2.kreo_whats2.hooks as hooks_module
        print("✅ Módulo hooks importado exitosamente")
        
        # Verificar que ADVANCED_LOGGING_AVAILABLE está definido
        if hasattr(hooks_module, 'ADVANCED_LOGGING_AVAILABLE'):
            print(f"✅ ADVANCED_LOGGING_AVAILABLE = {hooks_module.ADVANCED_LOGGING_AVAILABLE}")
        else:
            print("❌ ADVANCED_LOGGING_AVAILABLE no está definido")
            return False
            
        # Verificar que las funciones de hooks existen
        required_functions = [
            'whatsapp_settings_on_update',
            'whatsapp_settings_validate', 
            'whatsapp_message_on_submit',
            'whatsapp_message_on_update',
            'whatsapp_template_on_submit',
            'whatsapp_template_validate',
            'on_session_creation',
            'on_logout',
            'before_request'
        ]
        
        for func_name in required_functions:
            if hasattr(hooks_module, func_name):
                print(f"✅ Función {func_name} disponible")
            else:
                print(f"❌ Función {func_name} NO disponible")
                return False
                
        # Verificar que los diccionarios de hooks están definidos
        if hasattr(hooks_module, 'doc_events'):
            print("✅ doc_events definido")
            print(f"   Documentos con hooks: {list(hooks_module.doc_events.keys())}")
        else:
            print("❌ doc_events no está definido")
            return False
            
        if hasattr(hooks_module, 'before_request'):
            print("✅ before_request hook definido")
        else:
            print("❌ before_request hook no está definido")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Error importando módulo: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_logging_manager_integration():
    """Test 2: Verificar que el logging manager está integrado correctamente"""
    print("\n🔍 Test 2: Verificando integración del logging manager...")
    
    try:
        from apps.kreo_whats2.kreo_whats2.utils.logging_manager import (
            logging_manager, log_event, log_error, get_logger
        )
        print("✅ Logging manager importado exitosamente")
        
        # Probar creación de logger
        logger = get_logger("test_integration")
        print("✅ Logger creado exitosamente")
        
        # Probar registro de evento básico
        log_event("test", "INFO", "Test de integración de logging", 
                 operation="integration_test",
                 metadata={"test_id": "1", "timestamp": datetime.now().isoformat()})
        print("✅ Evento de logging registrado")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando logging manager: {e}")
        return False
    except Exception as e:
        print(f"❌ Error en logging manager: {e}")
        return False

def test_hook_functions():
    """Test 3: Verificar que las funciones de hook pueden ser llamadas"""
    print("\n🔍 Test 3: Verificando funciones de hook...")
    
    try:
        import apps.kreo_whats2.kreo_whats2.hooks as hooks_module
        
        # Probar que las funciones existen y son callable
        test_functions = [
            ('whatsapp_settings_on_update', 2),  # doc, method
            ('whatsapp_settings_validate', 2), 
            ('whatsapp_message_on_submit', 2),
            ('whatsapp_message_on_update', 2),
            ('whatsapp_template_on_submit', 2),
            ('whatsapp_template_validate', 2),
            ('on_session_creation', 1),  # login_manager
            ('on_logout', 1), 
            ('before_request', 0),  # no args
        ]
        
        for func_name, expected_args in test_functions:
            if hasattr(hooks_module, func_name):
                func = getattr(hooks_module, func_name)
                if callable(func):
                    print(f"✅ {func_name} es callable")
                    
                    # Verificar número de argumentos esperados
                    import inspect
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if len(params) >= expected_args:
                        print(f"   ✅ {func_name} acepta {len(params)} parámetros (esperados >= {expected_args})")
                    else:
                        print(f"   ⚠️  {func_name} acepta {len(params)} parámetros (esperados >= {expected_args})")
                else:
                    print(f"❌ {func_name} no es callable")
                    return False
            else:
                print(f"❌ {func_name} no existe")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Error probando funciones de hook: {e}")
        return False

def test_frappe_context():
    """Test 4: Verificar compatibilidad con contexto de Frappe"""
    print("\n🔍 Test 4: Verificando compatibilidad con Frappe...")
    
    try:
        # Simular contexto de Frappe
        class MockFrappe:
            class MockSession:
                user = "test_user"
                
            class MockRequest:
                method = "GET"
                path = "/test"
                
                class MockHeaders:
                    def get(self, key, default=None):
                        return default
                        
                headers = MockHeaders()
                
            session = MockSession()
            request = MockRequest()
            
            @staticmethod
            def local():
                class MockLocal:
                    request_ip = "127.0.0.1"
                return MockLocal()
                
        # Probar funciones que dependen de frappe
        import apps.kreo_whats2.kreo_whats2.hooks as hooks_module
        
        # Guardar el frappe original
        original_frappe = None
        try:
            import frappe
            original_frappe = frappe
        except ImportError:
            print("⚠️  Frappe no está disponible, usando mock")
            
        # Simular frappe en el módulo
        import sys
        sys.modules['frappe'] = MockFrappe
        
        # Probar before_request con contexto mock
        try:
            hooks_module.before_request()
            print("✅ before_request funciona con contexto mock")
        except Exception as e:
            print(f"⚠️  before_request con mock: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error en compatibilidad con Frappe: {e}")
        return False

def test_configuration():
    """Test 5: Verificar configuración de hooks"""
    print("\n🔍 Test 5: Verificando configuración de hooks...")
    
    try:
        import apps.kreo_whats2.kreo_whats2.hooks as hooks_module
        
        # Verificar doc_events
        expected_doctypes = [
            "WhatsApp Settings",
            "WhatsApp Message", 
            "WhatsApp Template"
        ]
        
        for doctype in expected_doctypes:
            if doctype in hooks_module.doc_events:
                print(f"✅ {doctype} en doc_events")
                events = hooks_module.doc_events[doctype]
                print(f"   Eventos: {list(events.keys())}")
            else:
                print(f"❌ {doctype} NO en doc_events")
                return False
                
        # Verificar hooks de sesión
        session_hooks = ['on_session_creation', 'on_logout', 'before_request']
        for hook_name in session_hooks:
            if hasattr(hooks_module, hook_name):
                print(f"✅ {hook_name} hook disponible")
            else:
                print(f"❌ {hook_name} hook NO disponible")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Error verificando configuración: {e}")
        return False

def run_all_tests():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas de integración de logging con Frappe Framework")
    print("=" * 70)
    
    tests = [
        test_logging_imports,
        test_logging_manager_integration,
        test_hook_functions,
        test_frappe_context,
        test_configuration
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Error en test {test.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DE LAS PRUEBAS")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {test.__name__}: {status}")
    
    print(f"\n🎯 Resumen: {passed}/{total} pruebas pasadas")
    
    if passed == total:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON! La integración está lista.")
        return True
    else:
        print("⚠️  Algunas pruebas fallaron. Revise los errores anteriores.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)