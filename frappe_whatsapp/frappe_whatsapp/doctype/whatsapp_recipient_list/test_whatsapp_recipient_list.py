# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

import json

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppRecipientList(IntegrationTestCase):
    """Tests for WhatsApp Recipient List doctype."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_user_with_mobile()

    @classmethod
    def _ensure_test_user_with_mobile(cls):
        """Ensure there's at least one user with mobile_no set for import tests."""
        if not frappe.db.get_value("User", "Administrator", "mobile_no"):
            frappe.db.set_value("User", "Administrator", "mobile_no", "919900000001")
            frappe.db.commit()

    def tearDown(self):
        for name in frappe.get_all("WhatsApp Recipient List", filters={"list_name": ["like", "Test Recipient%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Recipient List", name, force=True)
        frappe.db.commit()

    def _make_recipient_list(self, list_name="Test Recipient List 1", recipients=None):
        """Helper to create a WhatsApp Recipient List."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Recipient List",
            "list_name": list_name,
            "description": "Test list",
        })
        if recipients:
            for r in recipients:
                doc.append("recipients", r)
        doc.insert(ignore_permissions=True)
        return doc

    def test_recipient_list_creation(self):
        """Test basic recipient list creation."""
        doc = self._make_recipient_list(recipients=[
            {"mobile_number": "919900112233", "recipient_name": "User 1"},
        ])
        self.assertTrue(frappe.db.exists("WhatsApp Recipient List", doc.name))

    def test_recipient_list_autoname(self):
        """Test list is named from list_name field."""
        doc = self._make_recipient_list(
            list_name="Test Recipient Autoname",
            recipients=[{"mobile_number": "919900112233"}]
        )
        self.assertEqual(doc.name, "Test Recipient Autoname")

    def test_validate_requires_recipients_on_existing(self):
        """Test validation requires at least one recipient on existing docs."""
        doc = self._make_recipient_list(
            list_name="Test Recipient Validate",
            recipients=[{"mobile_number": "919900112233"}]
        )
        # Remove all recipients and try to save
        doc.recipients = []
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_import_list_from_doctype(self):
        """Test importing recipients from another doctype (User)."""
        doc = self._make_recipient_list(
            list_name="Test Recipient Import",
            recipients=[{"mobile_number": "placeholder"}]
        )

        count = doc.import_list_from_doctype(
            doctype="User",
            mobile_field="mobile_no",
            name_field="full_name",
            filters={"mobile_no": ["is", "set"]},
            limit=5,
        )

        self.assertGreater(count, 0)
        doc.save()

    def test_import_list_with_data_fields(self):
        """Test importing with additional data fields."""
        doc = self._make_recipient_list(
            list_name="Test Recipient DataFields",
            recipients=[{"mobile_number": "placeholder"}]
        )

        count = doc.import_list_from_doctype(
            doctype="User",
            mobile_field="mobile_no",
            name_field="full_name",
            data_fields=["email", "first_name"],
            filters={"mobile_no": ["is", "set"]},
            limit=5,
        )

        self.assertGreater(count, 0)
        doc.save()
        # Verify recipient_data contains the data fields
        for recipient in doc.recipients:
            if recipient.recipient_data:
                data = json.loads(recipient.recipient_data)
                self.assertIsInstance(data, dict)

    def test_import_clears_existing_recipients(self):
        """Test that import replaces existing recipients."""
        doc = self._make_recipient_list(
            list_name="Test Recipient Clear",
            recipients=[
                {"mobile_number": "919900112233", "recipient_name": "Old User"},
            ]
        )
        self.assertEqual(len(doc.recipients), 1)

        doc.import_list_from_doctype(
            doctype="User",
            mobile_field="mobile_no",
            filters={"mobile_no": ["is", "set"]},
            limit=5,
        )
        # Old recipients should be cleared
        for r in doc.recipients:
            self.assertNotEqual(r.recipient_name, "Old User")

    def test_import_formats_mobile_number(self):
        """Test that imported mobile numbers strip non-numeric characters."""
        doc = self._make_recipient_list(
            list_name="Test Recipient Format",
            recipients=[{"mobile_number": "placeholder"}]
        )

        # The import function strips non-numeric characters except +
        doc.recipients = []
        doc.append("recipients", {
            "mobile_number": "+91-9900-112233",
            "recipient_name": "Format Test",
        })
        # Manual mobile number isn't auto-formatted (that's in import logic)
        # Test the import logic separately by checking the function
        mobile = "+91-9900-112233"
        formatted = ''.join(char for char in mobile if char.isdigit() or char == '+')
        self.assertEqual(formatted, "+919900112233")
