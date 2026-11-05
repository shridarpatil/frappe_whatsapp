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
        """retry_failed re-sends failed rows AND resumes undispatched recipients.

        The bulk has two recipients (no rows yet) plus one Failed row, so retry
        should enqueue a resend for the failed row and a create for each of the
        two recipients that were never dispatched.
        """
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
            methods = [c.args[2] for c in mock_enqueue.call_args_list]
            # one resend for the failed row, one create for each undispatched recipient
            self.assertEqual(methods.count("resend_single_message"), 1)
            self.assertEqual(methods.count("create_single_message"), 2)
            resend_call = next(
                c for c in mock_enqueue.call_args_list if c.args[2] == "resend_single_message"
            )
            self.assertEqual(resend_call.kwargs.get("message_name"), failed_msg.name)

    def test_create_single_message_is_idempotent(self):
        """A duplicate create job for an already-dispatched recipient is a no-op.

        The guard runs before any insert, so this is independent of the send
        path: a recipient that already has a row for this campaign is skipped,
        leaving exactly one row.
        """
        doc = self._make_bulk_message(title="Test Bulk Idem")
        existing = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900119999",
            "message": "already dispatched",
            "message_type": "Manual",
            "content_type": "text",
            "status": "Queued",
            "bulk_message_reference": doc.name,
            "whatsapp_account": "Test WA Bulk Account",
        })
        existing.flags.ignore_validate = True
        existing.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

        # Duplicate create job for the same recipient -> skipped, no second row.
        doc.create_single_message({"mobile_number": "919900119999", "recipient_name": "Idem"})

        self.assertEqual(
            frappe.db.count("WhatsApp Message", {
                "bulk_message_reference": doc.name,
                "to": "919900119999",
            }),
            1,
        )

    def test_queue_messages_skips_already_dispatched(self):
        """queue_messages enqueues only recipients without a message row yet."""
        doc = self._make_bulk_message(
            title="Test Bulk Resume",
            recipients=[
                {"mobile_number": "919900220001", "recipient_name": "A"},
                {"mobile_number": "919900220002", "recipient_name": "B"},
            ],
        )
        # A was already dispatched on a previous (partial) run.
        already = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900220001",
            "message": "already",
            "message_type": "Manual",
            "content_type": "text",
            "status": "Queued",
            "bulk_message_reference": doc.name,
            "whatsapp_account": "Test WA Bulk Account",
        })
        already.flags.ignore_validate = True
        already.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.bulk_whatsapp_message.bulk_whatsapp_message.frappe.enqueue_doc"
        ) as mock_enqueue:
            doc.queue_messages()

        mock_enqueue.assert_called_once()
        enqueued = mock_enqueue.call_args.kwargs.get("recipient")
        self.assertEqual(enqueued.get("mobile_number"), "919900220002")

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
