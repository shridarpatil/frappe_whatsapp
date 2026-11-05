# Copyright (c) 2022, Shridhar Patil and Contributors
# See license.txt

import json
from unittest.mock import patch, MagicMock

import frappe
import pytz
from frappe.utils import (
    add_days,
    add_to_date,
    convert_utc_to_system_timezone,
    format_datetime,
    get_datetime,
    get_system_timezone,
    now_datetime,
)
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppTemplates(IntegrationTestCase):
    """Tests for WhatsApp Templates doctype."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_account()

    @classmethod
    def _ensure_test_account(cls):
        if not frappe.db.exists("WhatsApp Account", "Test WA Tmpl Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test WA Tmpl Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "tmpl_test_phone_id",
                "business_id": "tmpl_test_business_id",
                "app_id": "tmpl_test_app_id",
                "webhook_verify_token": "tmpl_test_verify_token",
                "is_default_incoming": 1,
                "is_default_outgoing": 1,
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def setUp(self):
        # Set password within each test's transaction scope
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("WhatsApp Account", "Test WA Tmpl Account", "test_tmpl_token", "token")
        # Clear ALL defaults then set ours (db.set_value bypasses on_update hooks)
        frappe.db.sql("UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0")
        frappe.db.set_value("WhatsApp Account", "Test WA Tmpl Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def tearDown(self):
        # Use SQL-level delete to avoid triggering on_trash (which calls get_settings)
        frappe.db.delete("WhatsApp Templates", {"template_name": ["like", "test_tmpl_%"]})
        frappe.db.delete("WhatsApp Templates", {"template_name": ["like", "test_msg_template%"]})
        frappe.db.delete("WhatsApp Template Edit Timeline", {"parent": ["like", "test_tmpl_%"]})
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

    def _add_meta_edits(self, doc, *hours_ago, status="APPROVED"):
        """Insert Meta edit history rows directly in DB."""
        for hours in hours_ago:
            doc.append("meta_edits", {"edited_on": add_to_date(now_datetime(), hours=-hours), "status": status}).db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries
        return frappe.get_doc("WhatsApp Templates", doc.name)

    def _make_template_without_hooks(self, **kwargs):
        """Create a template directly in DB to avoid Meta API calls."""
        template_name = kwargs.get("template_name", "test_tmpl_basic")
        language_code = kwargs.get("language_code", "en")
        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": template_name,
            "actual_name": template_name.lower().replace(" ", "_"),
            "template": kwargs.get("template", "Hello {{1}}"),
            "category": kwargs.get("category", "TRANSACTIONAL"),
            "language": kwargs.get("language", frappe.db.get_value("Language", {"language_code": "en"}) or "en"),
            "language_code": language_code,
            "whatsapp_account": kwargs.get("whatsapp_account", "Test WA Tmpl Account"),
            "status": kwargs.get("status", "APPROVED"),
            "id": kwargs.get("id", f"tmpl_id_{template_name}"),
            "header_type": kwargs.get("header_type", ""),
            "header": kwargs.get("header", ""),
            "footer": kwargs.get("footer", ""),
            "sample_values": kwargs.get("sample_values", ""),
        })
        doc.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries
        return frappe.get_doc("WhatsApp Templates", doc.name)

    def test_template_autoname(self):
        """Test template autoname format: template_name-language_code."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_autoname")
        self.assertEqual(doc.name, "test_tmpl_autoname-en")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_language_code_set_on_validate(self, mock_post):
        """Test language_code is derived from language field on validate."""
        mock_post.return_value = {}
        doc = self._make_template_without_hooks(template_name="test_tmpl_langcode")
        doc.language_code = ""
        doc.language = frappe.db.get_value("Language", {"language_code": "en"}) or "en"
        doc.validate()
        self.assertTrue(len(doc.language_code) > 0)

    def test_set_whatsapp_account_default(self):
        """Test whatsapp_account is set to default if missing."""
        doc = self._make_template_without_hooks(
            template_name="test_tmpl_default_acct",
            whatsapp_account=""
        )
        doc.whatsapp_account = ""
        doc.set_whatsapp_account()
        self.assertTrue(len(doc.whatsapp_account) > 0)

    def test_read_local_file_uses_file_doctype(self):
        """_read_local_file resolves through the File doctype, not raw paths."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_path")

        mock_file = MagicMock()
        mock_file.get_content.return_value = b"binary-content"
        with patch("frappe.get_doc", return_value=mock_file) as mock_get_doc:
            content = doc._read_local_file("/files/test_image.png")

        self.assertEqual(content, b"binary-content")
        mock_get_doc.assert_called_once_with("File", {"file_url": "/files/test_image.png"})

    def test_get_header_text(self):
        """Test get_header for TEXT header type."""
        doc = self._make_template_without_hooks(
            template_name="test_tmpl_hdr_text",
            header_type="TEXT",
            header="Order Update"
        )
        header = doc.get_header()
        self.assertEqual(header["type"], "header")
        self.assertEqual(header["format"], "TEXT")
        self.assertEqual(header["text"], "Order Update")

    def test_get_header_text_with_sample(self):
        """Test get_header for TEXT header with sample values."""
        doc = self._make_template_without_hooks(
            template_name="test_tmpl_hdr_sample",
            header_type="TEXT",
            header="Hello {{1}}",
            sample_values="John"
        )
        doc.sample = "John"
        header = doc.get_header()
        self.assertEqual(header["format"], "TEXT")
        self.assertIn("example", header)
        self.assertEqual(header["example"]["header_text"], ["John"])

    def test_get_settings(self):
        """Test get_settings loads WhatsApp Account credentials."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_settings")
        doc.get_settings()
        self.assertEqual(doc._url, "https://graph.facebook.com")
        self.assertEqual(doc._version, "v17.0")
        self.assertEqual(doc._business_id, "tmpl_test_business_id")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_after_insert_creates_template_on_meta(self, mock_post):
        """Test after_insert sends template to Meta API."""
        mock_post.return_value = {
            "id": "new_template_id_123",
            "status": "PENDING",
        }

        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": "test_tmpl_insert",
            "template": "Test body {{1}}",
            "sample_values": "World",
            "category": "TRANSACTIONAL",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Tmpl Account",
        })
        doc.insert(ignore_permissions=True)

        self.assertTrue(mock_post.called)
        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["name"], "test_tmpl_insert")
        self.assertEqual(sent_data["language"], "en")
        self.assertEqual(sent_data["category"], "TRANSACTIONAL")
        self.assertTrue(any(c["type"] == "BODY" for c in sent_data["components"]))

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_after_insert_with_footer(self, mock_post):
        """Test template creation includes footer in components."""
        mock_post.return_value = {"id": "tmpl_footer_id", "status": "PENDING"}

        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": "test_tmpl_footer",
            "template": "Body text",
            "footer": "Reply STOP to opt out",
            "category": "MARKETING",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Tmpl Account",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        footer_components = [c for c in sent_data["components"] if c["type"] == "FOOTER"]
        self.assertEqual(len(footer_components), 1)
        self.assertEqual(footer_components[0]["text"], "Reply STOP to opt out")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_after_insert_with_buttons(self, mock_post):
        """Test template creation includes buttons."""
        mock_post.return_value = {"id": "tmpl_btn_id", "status": "PENDING"}

        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": "test_tmpl_buttons",
            "template": "Click below",
            "category": "TRANSACTIONAL",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Tmpl Account",
        })
        doc.append("buttons", {
            "button_type": "Quick Reply",
            "button_label": "Yes",
        })
        doc.append("buttons", {
            "button_type": "Visit Website",
            "button_label": "Visit",
            "website_url": "https://example.com",
            "url_type": "Static",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        button_components = [c for c in sent_data["components"] if c["type"] == "BUTTONS"]
        self.assertEqual(len(button_components), 1)
        buttons = button_components[0]["buttons"]
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0]["type"], "QUICK_REPLY")
        self.assertEqual(buttons[1]["type"], "URL")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_on_trash_deletes_from_meta(self, mock_request, mock_post):
        """Test on_trash calls Meta API to delete template."""
        mock_post.return_value = {"id": "tmpl_trash_id", "status": "PENDING"}

        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": "test_tmpl_trash",
            "template": "Delete me",
            "category": "TRANSACTIONAL",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Tmpl Account",
        })
        doc.insert(ignore_permissions=True)

        mock_request.return_value = {}
        doc.delete()

        # Verify DELETE was called on Meta API
        self.assertTrue(mock_request.called)
        delete_call = mock_request.call_args
        self.assertEqual(delete_call[0][0], "DELETE")
        self.assertIn("message_templates", delete_call[0][1])

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_fetch_templates_from_meta(self, mock_post, mock_get, mock_get_password):
        """Test the fetch whitelisted function."""
        mock_get.return_value = {
            "data": [
                {
                    "name": "test_tmpl_fetched",
                    "status": "APPROVED",
                    "language": "en",
                    "category": "UTILITY",
                    "id": "fetched_tmpl_id",
                    "components": [
                        {"type": "BODY", "text": "Hello {{1}}, your order is ready"},
                        {"type": "FOOTER", "text": "Thank you"},
                    ]
                }
            ]
        }

        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch
        result = fetch()
        self.assertEqual(result, "Successfully fetched templates from meta")

    def test_upsert_doc_without_hooks(self):
        """Test upsert_doc_without_hooks inserts and updates correctly."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import upsert_doc_without_hooks

        doc = self._make_template_without_hooks(template_name="test_tmpl_upsert")

        # Update template text
        doc.template = "Updated body text"
        upsert_doc_without_hooks(doc, "WhatsApp Button", "buttons")

        doc.reload()
        self.assertEqual(doc.template, "Updated body text")

    def test_meta_edit_status_by_status(self):
        """Rejected and paused are unlimited; statuses other than approved show the review note."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_status")
        for status, color in {"REJECTED": "blue", "PAUSED": "blue", "PENDING": "orange"}.items():
            doc.status = status
            self.assertEqual(doc.get_meta_edit_status().color, color, status)

        doc.status = "APPROVED"
        edit_status = doc.get_meta_edit_status()
        self.assertEqual(edit_status.color, "blue")
        self.assertNotIn("Edits used", edit_status.message)

    def test_meta_edit_count_in_30_days(self):
        """Only approved edits inside 30 days count, and the count is shown below the limit."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_count")
        doc = self._add_meta_edits(doc, 30, 50, 100, 31 * 24)
        doc = self._add_meta_edits(doc, 1, status="REJECTED")

        edit_status = doc.get_meta_edit_status()
        self.assertEqual(edit_status.color, "blue")
        self.assertIn("3 of 10", edit_status.message)

    def test_meta_edit_within_24_hours_shows_next_edit_time(self):
        """An approved edit in the last 24 hours shows the next edit time 24 hours after it."""
        doc = self._add_meta_edits(self._make_template_without_hooks(template_name="test_tmpl_edit_24h"), 2)

        edit_status = doc.get_meta_edit_status()
        self.assertEqual(edit_status.color, "orange")
        self.assertEqual(edit_status.next_allowed, add_to_date(get_datetime(doc.meta_edits[0].edited_on), hours=24))

    def test_meta_edit_times_in_user_time_zone(self):
        """Note times are shown in the user's time zone."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_user_tz")
        doc.meta_last_updated_on = get_datetime("2026-11-03 10:00:00")
        user_tz = "UTC" if get_system_timezone() != "UTC" else "Asia/Kolkata"
        old_tz = frappe.db.get_value("User", frappe.session.user, "time_zone")
        frappe.db.set_value("User", frappe.session.user, "time_zone", user_tz)
        try:
            with patch(
                "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.now_datetime",
                return_value=get_datetime("2026-11-03 12:00:00"),
            ):
                edit_status = doc.get_meta_edit_status()
        finally:
            frappe.db.set_value("User", frappe.session.user, "time_zone", old_tz)

        user_time = pytz.timezone(get_system_timezone()).localize(doc.meta_last_updated_on).astimezone(pytz.timezone(user_tz))
        self.assertIn(format_datetime(user_time.replace(tzinfo=None), "d MMM yyyy, h:mm a"), edit_status.message)
        self.assertIn(format_datetime(add_days(user_time, 1).replace(tzinfo=None), "d MMM yyyy, h:mm a"), edit_status.message)

    def test_ten_meta_edits_in_30_days_shows_next_edit_time(self):
        """Ten approved edits in 30 days show the next edit time when the oldest leaves the window."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_30d")
        doc = self._add_meta_edits(doc, *range(25, 251, 25))

        edit_status = doc.get_meta_edit_status()
        oldest = min(get_datetime(e.edited_on) for e in doc.meta_edits)
        self.assertEqual(edit_status.color, "red")
        self.assertEqual(edit_status.next_allowed, add_days(oldest, 30))

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_successful_meta_edit_recorded(self, mock_post):
        """A successful edit at Meta adds a history row."""
        mock_post.return_value = {"success": True}
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_ok", category="UTILITY")
        doc.footer = "New footer"
        doc.save(ignore_permissions=True)

        doc.reload()
        self.assertEqual(len(doc.meta_edits), 1)
        self.assertEqual(doc.meta_edits[0].status, "APPROVED")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_failed_meta_edit_not_recorded(self, mock_post):
        """A failed edit at Meta adds no history row."""
        mock_post.side_effect = Exception("400 Client Error")
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_fail", category="UTILITY")
        doc.footer = "New footer"

        self.assertRaises(Exception, doc.save, ignore_permissions=True)
        doc.reload()
        self.assertEqual(len(doc.meta_edits), 0)

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_fetch_keeps_meta_edit_history(self, mock_get, mock_get_password):
        """Sync from Meta does not erase the edit history."""
        doc = self._add_meta_edits(self._make_template_without_hooks(template_name="test_tmpl_fetch_history"), 1)
        mock_get.return_value = {
            "data": [
                {
                    "name": doc.actual_name,
                    "status": "APPROVED",
                    "language": "en",
                    "category": "UTILITY",
                    "id": doc.id,
                    "components": [{"type": "BODY", "text": "Synced body"}],
                }
            ]
        }

        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch
        fetch()

        doc.reload()
        self.assertEqual(len(doc.meta_edits), 1)

    def test_meta_last_updated_within_24_hours_shows_next_edit_time(self):
        """Meta's last update in the last 24 hours shows the next edit time without our own history."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_edit_meta_time")
        doc.meta_last_updated_on = add_to_date(now_datetime(), hours=-2)

        edit_status = doc.get_meta_edit_status()
        self.assertEqual(edit_status.color, "orange")
        self.assertEqual(edit_status.next_allowed, add_to_date(doc.meta_last_updated_on, hours=24))

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_fetch_stores_meta_last_updated(self, mock_get, mock_get_password):
        """Sync from Meta asks for and stores Meta's last update time in system time."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_fetch_meta_time")
        mock_get.return_value = {
            "data": [
                {
                    "name": doc.actual_name,
                    "status": "APPROVED",
                    "language": "en",
                    "category": "UTILITY",
                    "id": doc.id,
                    "last_updated_time": "2026-09-05T04:51:55+0000",
                    "components": [{"type": "BODY", "text": "Synced body"}],
                }
            ]
        }

        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch
        fetch()

        self.assertIn("last_updated_time", mock_get.call_args.kwargs["params"]["fields"])
        doc.reload()
        expected = convert_utc_to_system_timezone(get_datetime("2026-09-05 04:51:55")).replace(tzinfo=None)
        self.assertEqual(get_datetime(doc.meta_last_updated_on), expected)
