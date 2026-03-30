# Copyright (c) 2022, Shridhar Patil and Contributors
# See license.txt

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppSettings(IntegrationTestCase):
    """Tests for WhatsApp Settings doctype."""

    def test_settings_exists(self):
        """Test WhatsApp Settings singleton exists."""
        settings = frappe.get_single("WhatsApp Settings")
        self.assertIsNotNone(settings)

    def test_settings_is_single(self):
        """Test that WhatsApp Settings is a Single doctype."""
        meta = frappe.get_meta("WhatsApp Settings")
        self.assertTrue(meta.issingle)
