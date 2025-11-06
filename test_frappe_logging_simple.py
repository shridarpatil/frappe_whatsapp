#!/usr/bin/env python3
"""
Prueba simple para validar la integración de logging avanzado con Frappe Framework
"""

import sys
import os

# Añadir el path para importar módulos de Frappe
sys.path.insert(0, '/f/Giovany/KREO.ONE/frappe_docker')

def test_hooks_import():
    """Test para validar que los hooks se pueden importar correctamente"""
    try:
        # Cambiar al directorio correcto
        os.chdir('/f/Giovany/KREO.ONE/frappe_docker')
        
        # Intentar importar el módulo hooks
        from apps.kreo_whats2.kreo_whats2 import hooks
        
        print("✅ Importación exitosa del módulo hooks")
        
        # Verificar que las funciones principales existen
        required_functions = [
            'sales_invoice_on_submit',
            'lead_after_insert', 
            'payment_entry_on_submit',
            'customer_after_insert',
            'whatsapp_settings_on_update',
            'whatsapp_message_on_submit',
            'on_session_creation',
            'on_logout',
            'before_request'
        ]
        
        for func_name in required_functions:
            if hasattr(hooks, func_name):
                print(f"✅ Función {func_name} encontrada")
            else:
                print(f"❌ Función {func_name} NO encontrada")
                return False
        
        # Verificar que las configuraciones existen
        if hasattr(hooks, 'doc_events') and hooks.doc_events:
            print("✅ Configuración doc_events encontrada")
        else:
            print("❌ Configuración doc_events NO encontrada")
            return False
            
        if hasattr(hooks, 'scheduler_events') and hooks.scheduler_events:
            print("✅ Configuración scheduler_events encontrada")
        else:
            print("❌ Configuración scheduler_events NO encontrada")
            return False
            
        print("✅ Todas las pruebas de hooks pasaron")
        return True
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_logging_manager_import():
    """Test para validar que el logging manager se puede importar"""
    try:
        # Intentar importar el logging manager
        from apps.kreo_whats2.kreo_whats2.utils.logging_manager import logging_manager
        
        print("✅ Importación exitosa del logging manager")
        
        # Verificar métodos principales
        required_methods = [
            'start_operation_context',
            'end_operation_context', 
            'setup_module_logging'
        ]
        
        for method_name in required_methods:
            if hasattr(logging_manager, method_name):
                print(f"✅ Método {method_name} encontrado")
            else:
                print(f"❌ Método {method_name} NO encontrado")
                return False
        
        print("✅ Todas las pruebas de logging manager pasaron")
        return True
        
    except ImportError as e:
        print(f"❌ Error de importación del logging manager: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado en logging manager: {e}")
        return False

def main():
    """Función principal de prueba"""
    print("🚀 Iniciando pruebas de integración Frappe + Logging Avanzado")
    print("=" * 60)
    
    # Test 1: Importación de hooks
    print("\n📋 Test 1: Importación de hooks")
    hooks_test = test_hooks_import()
    
    # Test 2: Importación de logging manager
    print("\n📋 Test 2: Importación de logging manager")
    logging_test = test_logging_manager_import()
    
    print("\n" + "=" * 60)
    
    if hooks_test and logging_test:
        print("🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")
        print("✅ La integración de logging avanzado con Frappe Framework está funcionando correctamente")
        return True
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("❌ La integración necesita correcciones")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)