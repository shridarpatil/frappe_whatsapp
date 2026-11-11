# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestBulkWhatsAppMessage(IntegrationTestCase):
    """Tests for Bulk WhatsApp Message doctype."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_account()
        cls._ensure_test_template()

    @classmethod
    def _ensure_test_account(cls):
        if not frappe.db.exists("WhatsApp Account", "Test WA Bulk Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test WA Bulk Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "bulk_test_phone_id",
                "business_id": "bulk_test_business_id",
                "app_id": "bulk_test_app_id",
                "webhook_verify_token": "bulk_test_verify_token",
                "is_default_incoming": 1,
                "is_default_outgoing": 1,
            })
            account.insert(ignore_permissions=True)
            from frappe.utils.password import set_encrypted_password
            set_encrypted_password("WhatsApp Account", account.name, "test_bulk_token", "token")
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    @classmethod
    def _ensure_test_template(cls):
        template_name = "test_bulk_template-en"
        if not frappe.db.exists("WhatsApp Templates", template_name):
            doc = frappe.get_doc({
                "doctype": "WhatsApp Templates",
                "template_name": "test_bulk_template",
                "actual_name": "test_bulk_template",
                "template": "Hello {{1}}, your bulk message",
                "sample_values": "User",
                "category": "MARKETING",
                "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
                "language_code": "en",
                "whatsapp_account": "Test WA Bulk Account",
                "status": "APPROVED",
                "id": "test_bulk_template_id",
            })
            doc.db_insert()
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def setUp(self):
        # Set password within each test's transaction scope
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("WhatsApp Account", "Test WA Bulk Account", "test_bulk_token", "token")
        # Clear ALL defaults then set ours (db.set_value bypasses on_update hooks)
        frappe.db.sql("UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0")
        frappe.db.set_value("WhatsApp Account", "Test WA Bulk Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def tearDown(self):
        for name in frappe.get_all("Bulk WhatsApp Message", filters={"title": ["like", "Test Bulk%"]}, pluck="name"):
            frappe.db.set_value("Bulk WhatsApp Message", name, "docstatus", 2)
            frappe.delete_doc("Bulk WhatsApp Message", name, force=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def _make_bulk_message(self, **kwargs):
        """Helper to create a Bulk WhatsApp Message."""
        doc = frappe.get_doc({
            "doctype": "Bulk WhatsApp Message",
            "title": kwargs.get("title", "Test Bulk Message 1"),
            "recipient_type": kwargs.get("recipient_type", "Individual"),
            "use_template": kwargs.get("use_template", 1),
            "template": kwargs.get("template", "test_bulk_template-en"),
            "variable_type": kwargs.get("variable_type", "Common"),
            "whatsapp_account": kwargs.get("whatsapp_account", "Test WA Bulk Account"),
            "template_variables": kwargs.get("template_variables"),
            "button_variables": kwargs.get("button_variables"),
        })
        recipients = kwargs.get("recipients", [
            {"mobile_number": "919900112233", "recipient_name": "User 1"},
            {"mobile_number": "919900112244", "recipient_name": "User 2"},
        ])
        for r in recipients:
            doc.append("recipients", r)
        doc.insert(ignore_permissions=True)
        return doc

    def test_bulk_message_creation(self):
        """Test basic bulk message creation."""
        doc = self._make_bulk_message()
        self.assertTrue(frappe.db.exists("Bulk WhatsApp Message", doc.name))
        self.assertEqual(doc.status, "Draft")

    def test_autoname_format(self):
        """Test bulk message autoname starts with BULK-WA-."""
        doc = self._make_bulk_message(title="Test Bulk Autoname")
        self.assertTrue(doc.name.startswith("BULK-WA-"))

    def test_validate_recipients_required(self):
        """Test that at least one recipient or list is required."""
        with self.assertRaises(frappe.ValidationError):
            doc = frappe.get_doc({
                "doctype": "Bulk WhatsApp Message",
                "title": "Test Bulk No Recipients",
                "recipient_type": "Individual",
                "use_template": 1,
                "template": "test_bulk_template-en",
                "whatsapp_account": "Test WA Bulk Account",
            })
            # No recipients added
            doc.insert(ignore_permissions=True)

    def test_recipient_count_set_on_validate(self):
        """Test that recipient_count is set during validation."""
        doc = self._make_bulk_message(title="Test Bulk Count")
        self.assertEqual(doc.recipient_count, 2)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_on_submit_queues_messages(self, mock_post):
        """Test that submitting queues the messages."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.bulk_test_1"}],
        }
        doc = self._make_bulk_message(title="Test Bulk Submit")
        doc.submit()
        doc.reload()
        self.assertEqual(doc.status, "Queued")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_create_single_message(self, mock_post):
        """Test creating a single message from bulk."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.bulk_single_1"}],
        }
        doc = self._make_bulk_message(title="Test Bulk Single")

        recipient = {
            "mobile_number": "919900112255",
            "recipient_name": "Single Test",
            "recipient_data": json.dumps({"name": "Single Test"}),
        }
        doc.create_single_message(recipient)

        self.assertTrue(
            frappe.db.exists("WhatsApp Message", {"to": "919900112255"})
        )

    def test_get_progress(self):
        """Test get_progress returns correct structure."""
        doc = self._make_bulk_message(title="Test Bulk Progress")
        progress = doc.get_progress()
        self.assertIn("total", progress)
        self.assertIn("sent", progress)
        self.assertIn("failed", progress)
        self.assertIn("queued", progress)
        self.assertIn("percent", progress)
        self.assertEqual(progress["total"], 2)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_retry_failed(self, mock_post):
        """Test retry_failed enqueues each failed message for re-send."""
        doc = self._make_bulk_message(title="Test Bulk Retry")
        # Create a failed message referencing this bulk
        failed_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112266",
            "message": "Failed msg",
            "message_type": "Manual",
            "content_type": "text",
            "status": "Failed",
            "bulk_message_reference": doc.name,
            "whatsapp_account": "Test WA Bulk Account",
            "message_id": "wamid.failed_bulk_1",
        })
        failed_msg.flags.ignore_validate = True
        failed_msg.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.bulk_whatsapp_message.bulk_whatsapp_message.frappe.enqueue_doc"
        ) as mock_enqueue:
            doc.retry_failed()
            mock_enqueue.assert_called_once()
            call_kwargs = mock_enqueue.call_args.kwargs
            self.assertEqual(call_kwargs.get("message_name"), failed_msg.name)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_resend_single_message(self, mock_post):
        """Test the worker entry actually re-sends and persists Success."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.bulk_retry_1"}],
        }

        doc = self._make_bulk_message(title="Test Bulk Resend Single")
        failed_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112277",
            "message": "Failed msg",
            "message_type": "Manual",
            "content_type": "text",
            "status": "Failed",
            "bulk_message_reference": doc.name,
            "whatsapp_account": "Test WA Bulk Account",
            "message_id": "wamid.failed_bulk_2",
        })
        failed_msg.flags.ignore_validate = True
        failed_msg.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

        doc.resend_single_message(failed_msg.name)

        failed_msg.reload()
        self.assertEqual(failed_msg.status, "Success")
        self.assertEqual(failed_msg.message_id, "wamid.bulk_retry_1")
        mock_post.assert_called_once()

    def test_validate_with_recipient_list(self):
        """Test validation with recipient_list type."""
        # Create a recipient list first
        rec_list = frappe.get_doc({
            "doctype": "WhatsApp Recipient List",
            "list_name": "Test Recipient Bulk List",
        })
        rec_list.append("recipients", {"mobile_number": "919900112277", "recipient_name": "List User"})
        rec_list.insert(ignore_permissions=True)

        doc = frappe.get_doc({
            "doctype": "Bulk WhatsApp Message",
            "title": "Test Bulk With List",
            "recipient_type": "Recipient List",
            "recipient_list": rec_list.name,
            "use_template": 1,
            "template": "test_bulk_template-en",
            "whatsapp_account": "Test WA Bulk Account",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.recipient_count, 1)

        # Cleanup
        frappe.delete_doc("WhatsApp Recipient List", rec_list.name, force=True)

    def _ensure_button_template(self, base_name, buttons, **fields):
        """Create an approved template with the given button rows (no Meta calls)."""
        template_name = f"{base_name}-en"
        if frappe.db.exists("WhatsApp Templates", template_name):
            return template_name
        tmpl = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": base_name,
            "actual_name": base_name,
            "template": "Hello",
            "category": "TRANSACTIONAL",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Bulk Account",
            "status": "APPROVED",
            "id": f"{base_name}_id",
            "name": template_name,
            **fields,
        })
        tmpl.flags.ignore_validate = True
        tmpl.db_insert()
        for idx, data in enumerate(buttons, start=1):
            frappe.get_doc({
                "doctype": "WhatsApp Button",
                "parent": template_name,
                "parenttype": "WhatsApp Templates",
                "parentfield": "buttons",
                "idx": idx,
                **data,
            }).db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries
        return template_name

    def _ensure_dynamic_button_template(self):
        return self._ensure_button_template(
            "test_bulk_dyn_template",
            [{"button_type": "Visit Website", "button_label": "Pay", "website_url": "https://example.com/pay/{{1}}", "url_type": "Dynamic"}],
            template="Hello {{1}}",
            sample_values="User",
        )

    @staticmethod
    def _url_buttons(call):
        sent_data = json.loads(call.kwargs["data"])
        return [c for c in sent_data["template"]["components"] if c.get("sub_type") == "url"]

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_unique_button_data_reaches_message(self, mock_post):
        """Unique mode: each recipient's Button Data fills the dynamic link button."""
        mock_post.return_value = {"messages": [{"id": "wamid.bulk_dyn_unique"}]}
        recipient = {
            "mobile_number": "919900112301",
            "recipient_name": "Asha",
            "recipient_data": json.dumps({"name": "Asha"}),
            "button_data": json.dumps({"pay_link": "INV-0042"}),
        }
        doc = self._make_bulk_message(
            title="Test Bulk Dyn Unique",
            template=self._ensure_dynamic_button_template(),
            variable_type="Unique",
            recipients=[recipient],
        )

        doc.create_single_message(recipient)

        self.assertEqual(
            self._url_buttons(mock_post.call_args)[0]["parameters"],
            [{"type": "text", "text": "INV-0042"}],
        )
        stored = frappe.db.get_value(
            "WhatsApp Message",
            {"to": "919900112301", "bulk_message_reference": doc.name},
            "button_param",
        )
        self.assertEqual(json.loads(stored), {"pay_link": "INV-0042"})

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_common_button_variables_reach_message(self, mock_post):
        """Common mode: Button Variables on the bulk message apply to every recipient."""
        mock_post.return_value = {"messages": [{"id": "wamid.bulk_dyn_common"}]}
        doc = self._make_bulk_message(
            title="Test Bulk Dyn Common",
            template=self._ensure_dynamic_button_template(),
            variable_type="Common",
            template_variables=json.dumps({"name": "Everyone"}),
            button_variables=json.dumps({"pay_link": "PROMO-1"}),
        )

        for recipient in doc.recipients:
            doc.create_single_message(recipient)

        self.assertEqual(mock_post.call_count, 2)
        for call in mock_post.call_args_list:
            self.assertEqual(
                self._url_buttons(call)[0]["parameters"],
                [{"type": "text", "text": "PROMO-1"}],
            )

    def test_validate_requires_button_values(self):
        """A template with a dynamic link button cannot be sent without values."""
        template = self._ensure_dynamic_button_template()

        # Common mode without Button Variables
        with self.assertRaises(frappe.ValidationError):
            self._make_bulk_message(title="Test Bulk Dyn No Common", template=template)

        # Unique mode with one recipient missing Button Data
        with self.assertRaises(frappe.ValidationError):
            self._make_bulk_message(
                title="Test Bulk Dyn No Unique",
                template=template,
                variable_type="Unique",
                recipients=[
                    {"mobile_number": "919900112302", "button_data": json.dumps({"pay_link": "A"})},
                    {"mobile_number": "919900112303"},
                ],
            )

        # Blank values do not count
        with self.assertRaises(frappe.ValidationError):
            self._make_bulk_message(
                title="Test Bulk Dyn Blank",
                template=template,
                button_variables=json.dumps({"pay_link": ""}),
            )

    def test_validate_button_values_with_recipient_list(self):
        """Unique mode reads Button Data from the recipient list rows."""
        template = self._ensure_dynamic_button_template()
        rec_list = frappe.get_doc({
            "doctype": "WhatsApp Recipient List",
            "list_name": "Test Recipient Bulk Dyn List",
        })
        rec_list.append("recipients", {
            "mobile_number": "919900112304",
            "button_data": json.dumps({"pay_link": "INV-1"}),
        })
        rec_list.append("recipients", {"mobile_number": "919900112305"})
        rec_list.insert(ignore_permissions=True)

        def make():
            return frappe.get_doc({
                "doctype": "Bulk WhatsApp Message",
                "title": "Test Bulk Dyn With List",
                "recipient_type": "Recipient List",
                "recipient_list": rec_list.name,
                "use_template": 1,
                "template": template,
                "variable_type": "Unique",
                "whatsapp_account": "Test WA Bulk Account",
            }).insert(ignore_permissions=True)

        try:
            with self.assertRaises(frappe.ValidationError):
                make()

            rec_list.recipients[1].button_data = json.dumps({"pay_link": "INV-2"})
            rec_list.save(ignore_permissions=True)
            self.assertEqual(make().recipient_count, 2)
        finally:
            frappe.delete_doc("WhatsApp Recipient List", rec_list.name, force=True)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_resend_keeps_button_value(self, mock_post):
        """Retrying a message re-sends the stored button value."""
        mock_post.return_value = {"messages": [{"id": "wamid.bulk_dyn_retry"}]}
        recipient = {
            "mobile_number": "919900112306",
            "recipient_data": json.dumps({"name": "Asha"}),
            "button_data": json.dumps({"pay_link": "INV-0099"}),
        }
        doc = self._make_bulk_message(
            title="Test Bulk Dyn Retry",
            template=self._ensure_dynamic_button_template(),
            variable_type="Unique",
            recipients=[recipient],
        )
        doc.create_single_message(recipient)
        message_name = frappe.db.get_value(
            "WhatsApp Message", {"to": "919900112306", "bulk_message_reference": doc.name}
        )
        frappe.db.set_value("WhatsApp Message", message_name, "status", "Failed")

        doc.resend_single_message(message_name)

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(
            self._url_buttons(mock_post.call_args)[0]["parameters"],
            [{"type": "text", "text": "INV-0099"}],
        )

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_failed_send_is_logged(self, mock_post):
        """A send that fails is recorded in the Error Log, not just counted."""
        mock_post.side_effect = Exception("Meta rejected the message")
        doc = self._make_bulk_message(title="Test Bulk Logged Failure")

        with patch("frappe.log_error") as mock_log:
            doc.create_single_message({"mobile_number": "919900112307", "recipient_data": "{}"})

        self.assertEqual(doc.status, "Partially Failed")
        titles = [call.kwargs.get("title", "") for call in mock_log.call_args_list]
        self.assertTrue(
            any(doc.name in title and "919900112307" in title for title in titles),
            f"no Error Log entry names the failed send: {titles}",
        )
