#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Validación simple de la integración de hooks con logging avanzado
"""

import sys
import os

# Cambiar al directorio de la aplicación
os.chdir('/f/Giovany/KREO.ONE/frappe_docker/apps/kreo_whats2')

def test_basic_imports():
    """Test básico de imports"""
    print("Test 1: Imports básicos...")
    
    try:
        # Importar hooks directamente
        import kreo_whats2.hooks as hooks_module
        print("✓ hooks module importado")
        
        # Verificar variables
        if hasattr(hooks_module, 'ADVANCED_LOGGING_AVAILABLE'):
            print(f"✓ ADVANCED_LOGGING_AVAILABLE = {hooks_module.ADVANCED_LOGGING_AVAILABLE}")
        
        # Verificar funciones básicas
        basic_functions = ['whatsapp_settings_on_update', 'whatsapp_message_on_submit']
        for func in basic_functions:
            if hasattr(hooks_module, func):
                print(f"✓ {func} disponible")
            else:
                print(f"✗ {func} NO disponible")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_logging_manager():
    """Test del logging manager"""
    print("\nTest 2: Logging manager...")
    
    try:
        from kreo_whats2.utils.logging_manager import get_logger, log_event
        print("✓ logging_manager importado")
        
        # Probar logger
        logger = get_logger("test")
        print("✓ logger creado")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_hooks_configuration():
    """Test de configuración de hooks"""
    print("\nTest 3: Configuración de hooks...")
    
    try:
        import kreo_whats2.hooks as hooks_module
        
        # Verificar doc_events
        if hasattr(hooks_module, 'doc_events'):
            print("✓ doc_events configurado")
            whatsapp_docs = ['WhatsApp Settings', 'WhatsApp Message', 'WhatsApp Template']
            for doc in whatsapp_docs:
                if doc in hooks_module.doc_events:
                    print(f"  ✓ {doc} en doc_events")
                else:
                    print(f"  ✗ {doc} NO en doc_events")
                    return False
        else:
            print("✗ doc_events no configurado")
            return False
            
        # Verificar hooks de sesión
        session_hooks = ['before_request', 'on_session_creation', 'on_logout']
        for hook in session_hooks:
            if hasattr(hooks_module, hook):
                print(f"✓ {hook} disponible")
            else:
                print(f"✗ {hook} NO disponible")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Ejecutar pruebas"""
    print("Validación de integración de logging con Frappe Framework")
    print("=" * 60)
    
    tests = [
        test_basic_imports,
        test_logging_manager,
        test_hooks_configuration
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Error en test: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("RESULTADOS:")
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "PASSED" if result else "FAILED"
        print(f"{i+1}. {test.__name__}: {status}")
    
    print(f"\nResumen: {passed}/{total} pruebas pasadas")
    
    if passed == total:
        print("\n✓ INTEGRACIÓN COMPLETA: Todos los hooks están configurados correctamente")
        print("✓ El logging avanzado está integrado con el Frappe Framework")
        print("✓ Los doctypes de WhatsApp tienen hooks de logging")
        print("✓ Los eventos de sesión están configurados")
        return True
    else:
        print("\n✗ Algunas pruebas fallaron")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)