# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now
from frappe_whatsapp.testing import IntegrationTestCase

from frappe_whatsapp.utils.bulk_messaging import (
    get_progress,
    import_recipients,
    process_scheduled_bulk_messages,
    retry_failed,
    schedule_bulk_messages,
)

QUEUE_MESSAGES = (
    "frappe_whatsapp.frappe_whatsapp.doctype.bulk_whatsapp_message"
    ".bulk_whatsapp_message.BulkWhatsAppMessage.queue_messages"
)


class TestBulkMessagingUtils(IntegrationTestCase):
    """Tests for bulk messaging utility functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_account()
        cls._ensure_test_template()
        cls._ensure_test_user_with_mobile()

    @classmethod
    def _ensure_test_account(cls):
        if not frappe.db.exists("WhatsApp Account", "Test WA BulkUtil Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test WA BulkUtil Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "bulkutil_test_phone_id",
                "business_id": "bulkutil_test_business_id",
                "app_id": "bulkutil_test_app_id",
                "webhook_verify_token": "bulkutil_test_verify_token",
                "is_default_incoming": 1,
                "is_default_outgoing": 1,
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    @classmethod
    def _ensure_test_template(cls):
        template_name = "test_bulkutil_template-en"
        if not frappe.db.exists("WhatsApp Templates", template_name):
            doc = frappe.get_doc({
                "doctype": "WhatsApp Templates",
                "template_name": "test_bulkutil_template",
                "actual_name": "test_bulkutil_template",
                "template": "Hello {{1}}",
                "sample_values": "User",
                "category": "MARKETING",
                "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
                "language_code": "en",
                "whatsapp_account": "Test WA BulkUtil Account",
                "status": "APPROVED",
                "id": "test_bulkutil_template_id",
            })
            doc.db_insert()
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    @classmethod
    def _ensure_test_user_with_mobile(cls):
        """Ensure there's at least one user with mobile_no set for import tests."""
        if not frappe.db.get_value("User", "Administrator", "mobile_no"):
            frappe.db.set_value("User", "Administrator", "mobile_no", "919900000001")
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def setUp(self):
        # Set password within each test's transaction scope
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("WhatsApp Account", "Test WA BulkUtil Account", "test_bulkutil_token", "token")
        # Clear ALL defaults then set ours (db.set_value bypasses on_update hooks)
        frappe.db.sql("UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0")
        frappe.db.set_value("WhatsApp Account", "Test WA BulkUtil Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def tearDown(self):
        for name in frappe.get_all("Bulk WhatsApp Message", filters={"title": ["like", "Test BulkUtil%"]}, pluck="name"):
            frappe.db.set_value("Bulk WhatsApp Message", name, "docstatus", 2)
            frappe.delete_doc("Bulk WhatsApp Message", name, force=True)
        for name in frappe.get_all("WhatsApp Recipient List", filters={"list_name": ["like", "Test BulkUtil%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Recipient List", name, force=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def _make_bulk_message(self, title="Test BulkUtil Msg"):
        """Create a bulk message for testing."""
        doc = frappe.get_doc({
            "doctype": "Bulk WhatsApp Message",
            "title": title,
            "recipient_type": "Individual",
            "use_template": 1,
            "template": "test_bulkutil_template-en",
            "variable_type": "Common",
            "whatsapp_account": "Test WA BulkUtil Account",
        })
        doc.append("recipients", {"mobile_number": "919900112233", "recipient_name": "User 1"})
        doc.append("recipients", {"mobile_number": "919900112244", "recipient_name": "User 2"})
        doc.insert(ignore_permissions=True)
        return doc

    def test_get_progress(self):
        """Test get_progress whitelisted function."""
        doc = self._make_bulk_message(title="Test BulkUtil Progress")
        progress = get_progress(doc.name)
        self.assertIn("total", progress)
        self.assertEqual(progress["total"], 2)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_retry_failed_util(self, mock_post):
        """Test retry_failed whitelisted function."""
        mock_post.return_value = {"messages": [{"id": "wamid.retry_util_1"}]}
        doc = self._make_bulk_message(title="Test BulkUtil Retry")

        # Create a failed message
        failed_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112255",
            "message": "Failed util msg",
            "message_type": "Manual",
            "content_type": "text",
            "status": "Failed",
            "bulk_message_reference": doc.name,
            "whatsapp_account": "Test WA BulkUtil Account",
            "message_id": "wamid.failed_util_1",
        })
        failed_msg.flags.ignore_validate = True
        failed_msg.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

        result = retry_failed(doc.name)
        self.assertTrue(result)

    def test_import_recipients(self):
        """Test import_recipients whitelisted function."""
        rec_list = frappe.get_doc({
            "doctype": "WhatsApp Recipient List",
            "list_name": "Test BulkUtil Import List",
        })
        rec_list.append("recipients", {"mobile_number": "placeholder"})
        rec_list.insert(ignore_permissions=True)

        count = import_recipients(
            list_name=rec_list.name,
            doctype="User",
            mobile_field="mobile_no",
            name_field="full_name",
            filters=json.dumps({"mobile_no": ["is", "set"]}),
            limit=5,
        )
        self.assertGreater(count, 0)

    def test_import_recipients_with_string_filters(self):
        """Test import_recipients handles string filters."""
        rec_list = frappe.get_doc({
            "doctype": "WhatsApp Recipient List",
            "list_name": "Test BulkUtil Import Str",
        })
        rec_list.append("recipients", {"mobile_number": "placeholder"})
        rec_list.insert(ignore_permissions=True)

        # Pass filters as string (as it would come from a whitelisted call)
        count = import_recipients(
            list_name=rec_list.name,
            doctype="User",
            mobile_field="mobile_no",
            filters='{"mobile_no": ["is", "set"]}',
            limit=5,
        )
        self.assertGreater(count, 0)

    def test_schedule_bulk_messages(self):
        """Test schedule_bulk_messages background job."""
        # This just ensures the function runs without error
        # when there are no queued bulk messages
        schedule_bulk_messages()

    def _make_due_scheduled_message(self, title):
        """Submit a scheduled campaign and back-date it so it is due.

        scheduled_time has to be in the future to pass validation, so the
        back-dating goes through db.set_value to bypass the controller.
        """
        doc = self._make_bulk_message(title=title)
        doc.db_set("scheduled_time", add_to_date(now(), hours=1))
        doc.submit()
        self.assertEqual(doc.status, "Scheduled")
        frappe.db.set_value(
            "Bulk WhatsApp Message", doc.name,
            "scheduled_time", add_to_date(now(), hours=-1),
        )
        return doc

    @patch(QUEUE_MESSAGES)
    def test_scheduled_campaign_gets_queued(self, mock_queue):
        """A due campaign is flipped to Queued and its recipients enqueued."""
        doc = self._make_due_scheduled_message("Test BulkUtil Due")

        process_scheduled_bulk_messages()

        self.assertEqual(mock_queue.call_count, 1)
        self.assertEqual(
            frappe.db.get_value("Bulk WhatsApp Message", doc.name, "status"),
            "Queued",
        )

    @patch(QUEUE_MESSAGES)
    def test_one_failing_campaign_does_not_block_the_others(self, mock_queue):
        """A campaign that raises while enqueuing must not abort the tick.

        Pre-fix the exception propagated out of the loop, so every campaign
        after the failing one was skipped and the whole transaction rolled
        back — while the already-enqueued jobs still went out, which is what
        produced duplicate sends on the following tick.
        """
        self._make_due_scheduled_message("Test BulkUtil Fail A")
        second = self._make_due_scheduled_message("Test BulkUtil Fail B")

        # raise on the first campaign only, succeed for the rest
        calls = []

        def _dispatch(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise Exception("enqueue blew up")

        mock_queue.side_effect = _dispatch

        process_scheduled_bulk_messages()

        self.assertEqual(len(calls), 2, "second campaign was never processed")
        self.assertEqual(
            frappe.db.get_value("Bulk WhatsApp Message", second.name, "status"),
            "Queued",
        )

    @patch(QUEUE_MESSAGES)
    def test_failed_campaign_stays_claimed_and_is_logged(self, mock_queue):
        """A partially-enqueued campaign must not revert to Scheduled.

        If it did, the next tick would re-select it and enqueue every
        recipient again, double-sending to everyone already dispatched.
        """
        doc = self._make_due_scheduled_message("Test BulkUtil Claim")
        mock_queue.side_effect = Exception("enqueue blew up")

        process_scheduled_bulk_messages()

        self.assertNotEqual(
            frappe.db.get_value("Bulk WhatsApp Message", doc.name, "status"),
            "Scheduled",
        )
        self.assertTrue(
            frappe.get_all(
                "Error Log",
                filters={"error": ["like", f"%{doc.name}%"]},
                limit=1,
            ),
            "failure was swallowed without an Error Log entry",
        )
