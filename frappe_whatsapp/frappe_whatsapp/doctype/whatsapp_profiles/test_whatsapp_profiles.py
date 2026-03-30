# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppProfiles(IntegrationTestCase):
    """Tests for WhatsApp Profiles doctype."""

    def setUp(self):
        # Clean up leftover profiles from other test classes (e.g., notification tests)
        for name in frappe.get_all("WhatsApp Profiles", filters={"number": ["like", "9199%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Profiles", name, force=True)
        frappe.db.commit()

    def tearDown(self):
        for name in frappe.get_all("WhatsApp Profiles", filters={"number": ["like", "9199%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Profiles", name, force=True)
        frappe.db.commit()

    def _make_profile(self, **kwargs):
        """Helper to create a WhatsApp Profile."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Profiles",
            "profile_name": kwargs.get("profile_name", "Test User"),
            "number": kwargs.get("number", "919900112233"),
            "whatsapp_account": kwargs.get("whatsapp_account", ""),
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_profile_creation(self):
        """Test basic profile creation."""
        doc = self._make_profile()
        self.assertTrue(frappe.db.exists("WhatsApp Profiles", doc.name))

    def test_format_whatsapp_number_strips_plus(self):
        """Test that leading + is stripped from number."""
        doc = self._make_profile(number="+919900112299")
        self.assertEqual(doc.number, "919900112299")

    def test_number_without_plus_unchanged(self):
        """Test that number without + is unchanged."""
        doc = self._make_profile(number="919900112234")
        self.assertEqual(doc.number, "919900112234")

    def test_set_title_with_name_and_number(self):
        """Test title is set to 'profile_name - number'."""
        doc = self._make_profile(profile_name="John Doe", number="919900112235")
        self.assertEqual(doc.title, "John Doe - 919900112235")

    def test_set_title_with_only_number(self):
        """Test title when only number is present."""
        doc = self._make_profile(profile_name="", number="919900112236")
        self.assertEqual(doc.title, "919900112236")

    def test_set_title_with_only_profile_name(self):
        """Test title when only profile_name is present (but number is required)."""
        doc = self._make_profile(profile_name="Jane Doe", number="919900112237")
        self.assertEqual(doc.title, "Jane Doe - 919900112237")

    def test_unique_number(self):
        """Test number field is unique."""
        self._make_profile(number="919900112238")
        with self.assertRaises(frappe.UniqueValidationError):
            self._make_profile(number="919900112238")
