# Copyright (c) 2022, Shridhar Patil and Contributors
# See license.txt

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppNotificationLog(IntegrationTestCase):
    """Tests for WhatsApp Notification Log doctype."""

    def tearDown(self):
        for name in frappe.get_all("WhatsApp Notification Log", filters={"template": ["like", "Test Log%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Notification Log", name, force=True)
        frappe.db.commit()

    def test_log_creation(self):
        """Test basic notification log creation."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Notification Log",
            "template": "Test Log Template",
            "meta_data": '{"status": "success"}'
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("WhatsApp Notification Log", doc.name))

    def test_log_with_json_metadata(self):
        """Test log stores JSON metadata correctly."""
        import json
        meta = {"messages": [{"id": "wamid.123"}], "contacts": [{"wa_id": "919900112233"}]}
        doc = frappe.get_doc({
            "doctype": "WhatsApp Notification Log",
            "template": "Test Log JSON",
            "meta_data": json.dumps(meta)
        })
        doc.insert(ignore_permissions=True)
        doc.reload()

        stored_meta = json.loads(doc.meta_data)
        self.assertEqual(stored_meta["messages"][0]["id"], "wamid.123")

    def test_log_with_error_metadata(self):
        """Test log stores error metadata."""
        import json
        meta = {"error": "Failed to send message: Invalid phone number"}
        doc = frappe.get_doc({
            "doctype": "WhatsApp Notification Log",
            "template": "Test Log Error",
            "meta_data": json.dumps(meta)
        })
        doc.insert(ignore_permissions=True)
        doc.reload()

        stored_meta = json.loads(doc.meta_data)
        self.assertIn("error", stored_meta)
