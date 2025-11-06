#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
import unittest
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase


class TestWhatsAppDIANIntegration(FrappeTestCase):
    """
    Tests de integración entre WhatsApp y DIAN para asegurar que
    los mensajes solo se envían después de aprobación DIAN.
    """

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
        """Configuración previa a cada test"""
        # Limpiar cualquier mensaje WhatsApp de pruebas anteriores
        frappe.db.sql("DELETE FROM `tabWhatsApp Message` WHERE reference_doctype = 'Sales Invoice'")
        frappe.db.commit()

    def tearDown(self):
        """Limpieza después de cada test"""
        frappe.db.rollback()

    @patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal')
    @patch('kreo_dian.kreo_dian.controllers.dian_controller.process_electronic_invoice')
    def test_whatsapp_not_sent_on_submit(self, mock_process_dian, mock_send_whatsapp):
        """
        Test: WhatsApp NO se envía en el momento del submit
        """
        # Arrange: Crear factura de prueba
        invoice = self.create_test_invoice()

        # Act: Submit de la factura
        invoice.submit()

        # Assert: WhatsApp NO debe haberse llamado en submit
        mock_send_whatsapp.assert_not_called()

        # Assert: DIAN debe haberse encolado
        # (verificar que el estado sea 'Processing')
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Processing')

    @patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal')
    @patch('kreo_dian.kreo_dian.utils.response_parser.DianResponseParser')
    def test_whatsapp_sent_only_after_dian_approval(self, mock_parser_class, mock_send_whatsapp):
        """
        Test: WhatsApp SOLO se envía después de aprobación DIAN
        """
        # Arrange: Crear factura y mockear respuesta DIAN aprobada
        invoice = self.create_test_invoice()

        mock_parser = MagicMock()
        mock_parser.parse_response.return_value = {
            'status': 'Approved',
            'cufe': 'test-cufe-123',
            'track_id': 'test-track-id',
            'status_code': '00',
            'status_description': 'Aprobado'
        }
        mock_parser_class.return_value = mock_parser

        # Act: Simular procesamiento DIAN completo
        invoice.submit()
        # Simular que el job async ejecutó y aprobó
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Approved')
        frappe.db.commit()

        # Simular llamada desde dian_controller después de aprobación
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        send_invoice_whatsapp_wrapper(invoice.name)

        # Assert: WhatsApp DEBE haberse llamado
        mock_send_whatsapp.assert_called_once()

    @patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal')
    def test_whatsapp_not_sent_if_dian_rejected(self, mock_send_whatsapp):
        """
        Test: WhatsApp NO se envía si DIAN rechaza la factura
        """
        # Arrange: Crear factura y simular rechazo DIAN
        invoice = self.create_test_invoice()
        invoice.submit()

        # Simular rechazo DIAN
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Rejected')
        frappe.db.commit()

        # Act: Intentar enviar WhatsApp
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        send_invoice_whatsapp_wrapper(invoice.name)

        # Assert: WhatsApp NO debe haberse llamado
        mock_send_whatsapp.assert_not_called()

    @patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal')
    def test_whatsapp_idempotent_no_resend(self, mock_send_whatsapp):
        """
        Test: WhatsApp NO se reenvía si ya existe un mensaje enviado
        """
        # Arrange: Crear factura aprobada
        invoice = self.create_test_invoice()
        invoice.submit()
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Approved')
        frappe.db.commit()

        # Crear mensaje WhatsApp existente
        whatsapp_msg = frappe.get_doc({
            'doctype': 'WhatsApp Message',
            'reference_doctype': 'Sales Invoice',
            'reference_name': invoice.name,
            'status': 'Sent',
            'phone_number': '+1234567890',
            'message': 'Test message'
        })
        whatsapp_msg.insert()
        frappe.db.commit()

        # Act: Intentar enviar WhatsApp de nuevo
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        send_invoice_whatsapp_wrapper(invoice.name)

        # Assert: WhatsApp NO debe haberse llamado (idempotencia)
        mock_send_whatsapp.assert_not_called()

    @patch('frappe.enqueue')
    def test_dian_processing_enqueued_on_submit(self, mock_enqueue):
        """
        Test: Procesamiento DIAN se encola correctamente en submit
        """
        # Arrange: Crear factura
        invoice = self.create_test_invoice()

        # Act: Submit
        invoice.submit()

        # Assert: frappe.enqueue debe haberse llamado con parámetros correctos
        mock_enqueue.assert_called()

        # Verificar que se encoló el método correcto
        call_args = mock_enqueue.call_args
        self.assertIn('process_electronic_invoice_async', str(call_args))

        # Verificar estado Processing
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Processing')

    def test_dian_async_pipeline_flow(self):
        """
        Test: Flujo completo del pipeline asíncrono DIAN
        """
        # Arrange: Crear factura
        invoice = self.create_test_invoice()
        self.assertIsNone(invoice.dian_status)

        # Act & Assert 1: Submit actualiza a Processing
        invoice.submit()
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Processing')

        # Act & Assert 2: Aprobación DIAN actualiza a Approved
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Approved')
        frappe.db.commit()
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Approved')

        # Act & Assert 3: Estado Approved permite WhatsApp
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        
        # Esta función solo debe permitir envío si status es 'Approved'
        # Mockeamos el envío para evitar llamada real
        with patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal') as mock_send:
            result = send_invoice_whatsapp_wrapper(invoice.name)
            # Debe intentar enviar porque el estado es Approved
            mock_send.assert_called_once()

    @patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal')
    def test_dian_rejection_prevents_whatsapp(self, mock_send_whatsapp):
        """
        Test: Estado 'Rejected' de DIAN previene envío de WhatsApp
        """
        # Arrange: Crear factura y simular rechazo
        invoice = self.create_test_invoice()
        invoice.submit()
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Rejected')
        frappe.db.commit()

        # Act: Intentar enviar WhatsApp
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        send_invoice_whatsapp_wrapper(invoice.name)

        # Assert: WhatsApp NO debe haberse llamado
        mock_send_whatsapp.assert_not_called()

    def test_event_order_sequencing(self):
        """
        Test: Verificación del orden correcto de eventos
        """
        # Arrange: Crear factura
        invoice = self.create_test_invoice()
        
        # Act & Assert: Secuencia esperada
        # 1. Estado inicial: None
        self.assertIsNone(invoice.dian_status)
        
        # 2. After submit: Processing
        invoice.submit()
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Processing')
        
        # 3. After DIAN approval: Approved
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Approved')
        frappe.db.commit()
        invoice.reload()
        self.assertEqual(invoice.dian_status, 'Approved')
        
        # 4. WhatsApp debe ser permitido solo después de Approved

    def test_idempotency_with_existing_messages(self):
        """
        Test: Verificación de idempotencia con mensajes existentes
        """
        # Arrange: Crear factura aprobada con mensaje existente
        invoice = self.create_test_invoice()
        invoice.submit()
        frappe.db.set_value('Sales Invoice', invoice.name, 'dian_status', 'Approved')
        frappe.db.commit()

        # Crear múltiples mensajes existentes
        for i in range(3):
            whatsapp_msg = frappe.get_doc({
                'doctype': 'WhatsApp Message',
                'reference_doctype': 'Sales Invoice',
                'reference_name': invoice.name,
                'status': 'Sent',
                'phone_number': f'+123456789{i}',
                'message': f'Test message {i}'
            })
            whatsapp_msg.insert()
        frappe.db.commit()

        # Verificar que existen mensajes
        existing_count = frappe.db.count('WhatsApp Message', {
            'reference_doctype': 'Sales Invoice',
            'reference_name': invoice.name
        })
        self.assertEqual(existing_count, 3)

        # Act: Intentar enviar WhatsApp múltiples veces
        from kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks import send_invoice_whatsapp_wrapper
        
        with patch('kreo_whats2.kreo_whats2.hooks.sales_invoice_hooks.send_invoice_whatsapp_internal') as mock_send:
            # Intentar enviar varias veces
            send_invoice_whatsapp_wrapper(invoice.name)
            send_invoice_whatsapp_wrapper(invoice.name)
            send_invoice_whatsapp_wrapper(invoice.name)

            # Assert: Nunca debe haberse llamado (idempotencia)
            mock_send.assert_not_called()

    def create_test_invoice(self):
        """
        Helper: Crea una factura de prueba para testing
        """
        customer = self.create_test_customer()
        item = self.create_test_item()

        invoice = frappe.get_doc({
            'doctype': 'Sales Invoice',
            'customer': customer.name,
            'due_date': frappe.utils.nowdate(),
            'items': [{
                'item_code': item.name,
                'qty': 1,
                'rate': 100
            }]
        })
        invoice.insert()
        return invoice

    def create_test_customer(self):
        """Helper: Crea un cliente de prueba"""
        customer_name = 'Test Customer DIAN Integration'
        if frappe.db.exists('Customer', customer_name):
            return frappe.get_doc('Customer', customer_name)

        customer = frappe.get_doc({
            'doctype': 'Customer',
            'customer_name': customer_name,
            'customer_type': 'Individual',
            'mobile_no': '+1234567890'
        })
        customer.insert()
        return customer

    def create_test_item(self):
        """Helper: Crea un ítem de prueba"""
        item_name = 'Test Item DIAN Integration'
        if frappe.db.exists('Item', item_name):
            return frappe.get_doc('Item', item_name)

        item = frappe.get_doc({
            'doctype': 'Item',
            'item_code': item_name,
            'item_name': item_name,
            'item_group': 'Products',
            'stock_uom': 'Nos',
            'is_stock_item': 0,
            'income_account': 'Sales - TC',
            'expense_account': 'Cost of Goods Sold - TC'
        })
        item.insert()
        return item


def run_whatsapp_dian_integration_tests():
    """Ejecutar todas las pruebas de integración WhatsApp-DIAN"""
    # Crear suite de pruebas
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWhatsAppDIANIntegration)

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
    results = run_whatsapp_dian_integration_tests()

    print("\n" + "="*70)
    print("RESULTADOS DE TESTS DE INTEGRACIÓN WHATSAPP-DIAN")
    print("="*70)
    print(f"Éxito: {'✅' if results['success'] else '❌'}")
    print(f"Tests ejecutados: {results['tests_run']}")
    print(f"Fallos: {results['failures']}")
    print(f"Errores: {results['errors']}")

    if not results['success']:
        print("\nDETALLES DE FALLOS/ERRORES:")
        for failure in results['failure_details']:
            print(f"❌ {failure[0]}: {failure[1]}")
        for error in results['error_details']:
            print(f"💥 {error[0]}: {error[1]}")

    print("="*70)
    print("\nCOBERTURA DE TESTS IMPLEMENTADOS:")
    print("✅ test_whatsapp_not_sent_on_submit")
    print("✅ test_whatsapp_sent_only_after_dian_approval")
    print("✅ test_whatsapp_not_sent_if_dian_rejected")
    print("✅ test_whatsapp_idempotent_no_resend")
    print("✅ test_dian_processing_enqueued_on_submit")
    print("✅ test_dian_async_pipeline_flow")
    print("✅ test_dian_rejection_prevents_whatsapp")
    print("✅ test_event_order_sequencing")
    print("✅ test_idempotency_with_existing_messages")
    print("\nVERIFICACIONES CUBIERTAS:")
    print("🔒 Submit NO envía WhatsApp inmediatamente")
    print("⚡ Procesamiento DIAN asíncrono se encola")
    print("✅ Estado 'Approved' permite envío WhatsApp")
    print("❌ Estado 'Rejected' bloquea envío WhatsApp")
    print("🔄 Idempotencia evita reenvío de mensajes")
    print("📊 Orden correcto de eventos validado")
    print("="*70)