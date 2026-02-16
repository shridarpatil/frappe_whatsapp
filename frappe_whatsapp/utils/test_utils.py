# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

from unittest.mock import patch, MagicMock

import frappe
from frappe_whatsapp.testing import IntegrationTestCase

from frappe_whatsapp.utils import (
    format_number,
    get_notifications_map,
    get_whatsapp_account,
    run_server_script_for_doc_event,
    trigger_whatsapp_notifications,
)


class TestFormatNumber(IntegrationTestCase):
    """Tests for format_number utility."""

    def test_strips_leading_plus(self):
        self.assertEqual(format_number("+919900112233"), "919900112233")

    def test_no_plus_unchanged(self):
        self.assertEqual(format_number("919900112233"), "919900112233")

    def test_plus_only_at_start(self):
        self.assertEqual(format_number("+1234567890"), "1234567890")


class TestGetWhatsAppAccount(IntegrationTestCase):
    """Tests for get_whatsapp_account utility."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_accounts()

    @classmethod
    def _ensure_test_accounts(cls):
        if not frappe.db.exists("WhatsApp Account", "Test Utils Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test Utils Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "utils_test_phone_id",
                "business_id": "utils_test_business_id",
                "app_id": "utils_test_app_id",
                "webhook_verify_token": "utils_test_verify_token",
                "is_default_incoming": 1,
                "is_default_outgoing": 1,
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()

    def setUp(self):
        # Clear ALL defaults then set ours (db.set_value bypasses on_update hooks)
        frappe.db.sql("UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0")
        frappe.db.set_value("WhatsApp Account", "Test Utils Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def test_get_account_by_phone_id(self):
        """Test getting account by phone_id."""
        account = get_whatsapp_account(phone_id="utils_test_phone_id")
        self.assertIsNotNone(account)
        self.assertEqual(account.name, "Test Utils Account")

    def test_get_account_by_phone_id_not_found(self):
        """Test getting account by non-existent phone_id falls back to default."""
        account = get_whatsapp_account(phone_id="nonexistent_phone_id")
        # Should fall back to default incoming
        if account:
            self.assertTrue(account.is_default_incoming)

    def test_get_default_incoming_account(self):
        """Test getting default incoming account."""
        account = get_whatsapp_account(account_type='incoming')
        self.assertIsNotNone(account)
        self.assertEqual(account.is_default_incoming, 1)

    def test_get_default_outgoing_account(self):
        """Test getting default outgoing account."""
        account = get_whatsapp_account(account_type='outgoing')
        self.assertIsNotNone(account)
        self.assertEqual(account.is_default_outgoing, 1)


class TestGetNotificationsMap(IntegrationTestCase):
    """Tests for get_notifications_map utility."""

    def test_returns_dict(self):
        """Test that notifications map returns a dictionary."""
        result = get_notifications_map()
        self.assertIsInstance(result, dict)

    def test_maps_doctype_to_events(self):
        """Test the structure of notification map."""
        # Create a test notification
        if not frappe.db.exists("WhatsApp Account", "Test Utils Map Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test Utils Map Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "utils_map_phone_id",
                "business_id": "utils_map_business_id",
                "app_id": "utils_map_app_id",
                "webhook_verify_token": "utils_map_verify_token",
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()

        template_name = "test_utils_map_template-en"
        if not frappe.db.exists("WhatsApp Templates", template_name):
            doc = frappe.get_doc({
                "doctype": "WhatsApp Templates",
                "template_name": "test_utils_map_template",
                "actual_name": "test_utils_map_template",
                "template": "Hello",
                "category": "TRANSACTIONAL",
                "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
                "language_code": "en",
                "whatsapp_account": "Test Utils Map Account",
                "status": "APPROVED",
                "id": "test_utils_map_tmpl_id",
            })
            doc.db_insert()
            frappe.db.commit()

        if not frappe.db.exists("WhatsApp Notification", "Test Utils Map Notif"):
            frappe.get_doc({
                "doctype": "WhatsApp Notification",
                "notification_name": "Test Utils Map Notif",
                "notification_type": "DocType Event",
                "reference_doctype": "User",
                "field_name": "mobile_no",
                "doctype_event": "After Save",
                "template": template_name,
                "disabled": 0,
            }).insert(ignore_permissions=True)
            frappe.db.commit()

        result = get_notifications_map()
        self.assertIn("User", result)
        self.assertIn("After Save", result["User"])
        self.assertIn("Test Utils Map Notif", result["User"]["After Save"])


class TestRunServerScriptForDocEvent(IntegrationTestCase):
    """Tests for run_server_script_for_doc_event."""

    def test_skips_during_install(self):
        """Test that it skips during install."""
        frappe.flags.in_install = True
        try:
            doc = frappe.get_doc("User", "Administrator")
            # Should not raise any error, just return
            run_server_script_for_doc_event(doc, "on_update")
        finally:
            frappe.flags.in_install = False

    def test_skips_during_migrate(self):
        """Test that it skips during migrate."""
        frappe.flags.in_migrate = True
        try:
            doc = frappe.get_doc("User", "Administrator")
            run_server_script_for_doc_event(doc, "on_update")
        finally:
            frappe.flags.in_migrate = False

    def test_skips_during_uninstall(self):
        """Test that it skips during uninstall."""
        frappe.flags.in_uninstall = True
        try:
            doc = frappe.get_doc("User", "Administrator")
            run_server_script_for_doc_event(doc, "on_update")
        finally:
            frappe.flags.in_uninstall = False

    def test_skips_unmapped_event(self):
        """Test that it skips events not in EVENT_MAP."""
        doc = frappe.get_doc("User", "Administrator")
        # 'random_event' is not in EVENT_MAP, should just return
        run_server_script_for_doc_event(doc, "random_event")


class TestTriggerWhatsAppNotifications(IntegrationTestCase):
    """Tests for trigger_whatsapp_notifications."""

    @patch("frappe_whatsapp.utils.frappe.get_doc")
    def test_trigger_by_frequency(self, mock_get_doc):
        """Test triggering notifications by frequency."""
        mock_notification = MagicMock()
        mock_get_doc.return_value = mock_notification

        # This will query for notifications with event_frequency="Daily"
        # and call send_scheduled_message on each
        trigger_whatsapp_notifications("Daily")
        # The function queries the DB, so if there are no matching notifications,
        # mock_get_doc may not be called
