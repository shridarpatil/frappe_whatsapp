# Copyright (c) 2022, Shridhar Patil and Contributors
# See license.txt

import json
from unittest.mock import patch, MagicMock

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppTemplates(IntegrationTestCase):
    """Tests for WhatsApp Templates doctype."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # setUp() clears the default flags on every WhatsApp Account so the
        # test account is unambiguously the default. On a site that already has
        # real accounts that is destructive, so snapshot the flags here and put
        # them back in tearDownClass.
        cls._account_defaults = frappe.get_all(
            "WhatsApp Account",
            fields=["name", "is_default_incoming", "is_default_outgoing"],
        )
        cls._ensure_test_account()

    @classmethod
    def tearDownClass(cls):
        for row in getattr(cls, "_account_defaults", []):
            if frappe.db.exists("WhatsApp Account", row.name):
                frappe.db.set_value(
                    "WhatsApp Account",
                    row.name,
                    {
                        "is_default_incoming": row.is_default_incoming,
                        "is_default_outgoing": row.is_default_outgoing,
                    },
                    update_modified=False,
                )
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- restore site config the fixtures overwrote
        super().tearDownClass()

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
        # Clear defaults on OTHER accounts then set ours (db.set_value bypasses
        # on_update hooks). tearDownClass restores the original flags.
        frappe.db.sql(
            "UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0 WHERE name != %s",
            "Test WA Tmpl Account",
        )
        frappe.db.set_value("WhatsApp Account", "Test WA Tmpl Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def tearDown(self):
        # Use SQL-level delete to avoid triggering on_trash (which calls get_settings)
        frappe.db.delete("WhatsApp Templates", {"template_name": ["like", "test_tmpl_%"]})
        frappe.db.delete("WhatsApp Templates", {"template_name": ["like", "test_msg_template%"]})
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

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

    def test_partial_variable_mapping_not_persisted(self):
        """Fix #1: Test partial variable mapping does not persist field_names."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import save_template
        payload = {
            "template_name": "test_tmpl_partial_map",
            "body": "Hello {{1}}, order {{2}} for {{3}}",
            "category": "UTILITY",
            "language": "en",
            "sample_values": ["Val1", "Val2", "Val3"],
            "field_names": ["", "customer_name", ""],
        }
        res = save_template(payload, submit=0)
        doc = frappe.get_doc("WhatsApp Templates", res["name"])
        self.assertIsNone(doc.field_names)

        # Full mapping persists
        payload["field_names"] = ["name", "customer_name", "owner"]
        res2 = save_template(payload, submit=0, name=res["name"])
        doc2 = frappe.get_doc("WhatsApp Templates", res2["name"])
        self.assertIsNotNone(doc2.field_names)

    def test_comma_in_sample_values(self):
        """Fix #2: Test sample values with commas are serialized as JSON and parsed cleanly."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import save_template, load_template
        payload = {
            "template_name": "test_tmpl_comma_sample",
            "body": "Amount {{1}}, address {{2}}",
            "category": "UTILITY",
            "language": "en",
            "sample_values": ["$1,234.00", "Main Street, NY"],
        }
        res = save_template(payload, submit=0)
        doc = frappe.get_doc("WhatsApp Templates", res["name"])
        self.assertTrue(doc.sample_values.startswith("["))

        loaded = load_template(res["name"])
        self.assertEqual(loaded["sample_values"], ["$1,234.00", "Main Street, NY"])

    def test_non_contiguous_variables_rejected(self):
        """Fix #3: Test non-contiguous body variables raise validation error."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import save_template
        payload = {
            "template_name": "test_tmpl_non_contiguous",
            "body": "Hello {{1}}, your item {{3}} is ready",
            "category": "UTILITY",
            "language": "en",
            "sample_values": ["Val1", "Val3"],
        }
        with self.assertRaises(frappe.ValidationError):
            save_template(payload, submit=0)

    def _append_button(self, doc, **values):
        """Attach a WhatsApp Button child row to an already-inserted template."""
        btn = doc.append("buttons", values)
        btn.name = None
        btn.insert(ignore_permissions=True)
        return btn

    def test_unsupported_buttons_locks_template(self):
        """Fix #4: An unmappable button type locks the template on its own.

        `id` is deliberately blank: with a Meta id present `_is_locked` would
        return True via `bool(doc.id)` regardless, so the assertion would pass
        even if the unsupported-button clause were removed.
        """
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import load_template, save_template
        doc = self._make_template_without_hooks(template_name="test_tmpl_flow_btn", id="", status="Pending")
        self._append_button(doc, button_type="Flow", button_label="Start Flow")

        loaded = load_template(doc.name)
        self.assertTrue(loaded["locked"], "Flow button alone must lock the template")
        self.assertTrue(any(b["unsupported"] for b in loaded["buttons"]))

        payload = {
            "template_name": "test_tmpl_flow_btn",
            "body": "Body text",
            "category": "UTILITY",
            "language": "en",
        }
        with self.assertRaises(frappe.ValidationError):
            save_template(payload, submit=0, name=doc.name)

    def test_supported_buttons_draft_not_locked(self):
        """Control for Fix #4: a draft with only mappable buttons stays editable."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import load_template
        doc = self._make_template_without_hooks(template_name="test_tmpl_reply_btn", id="", status="Pending")
        self._append_button(doc, button_type="Quick Reply", button_label="Yes")

        loaded = load_template(doc.name)
        self.assertFalse(loaded["locked"], "Quick Reply draft must remain editable")
        self.assertFalse(any(b["unsupported"] for b in loaded["buttons"]))

    def test_unsupported_button_kind_rejected_on_save(self):
        """Fix #4 (duplicate path): an unmappable kind must not be silently dropped.

        duplicateTemplate() copies client state verbatim, so a Flow/MPM/Catalog
        button reaches save_template as an unknown `kind`. Previously it was
        skipped and the copy saved with no buttons at all.
        """
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import save_template
        payload = {
            "template_name": "test_tmpl_dup_flow",
            "body": "Body text",
            "category": "UTILITY",
            "language": "en",
            "buttons": [{"kind": "Flow", "label": "Start Flow"}],
        }
        with self.assertRaises(frappe.ValidationError):
            save_template(payload, submit=0)
        self.assertFalse(frappe.db.exists("WhatsApp Templates", {"template_name": "test_tmpl_dup_flow"}))

    def test_text_header_sample_and_media_draft_preserved(self):
        """Fix #5: Test TEXT header sample preservation and IMAGE header type preservation on draft save."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import save_template, load_template
        payload = {
            "template_name": "test_tmpl_hdr_preservation",
            "body": "Body text",
            "category": "UTILITY",
            "language": "en",
            "header": {"type": "TEXT", "text": "Header {{1}}", "sample": "HeaderSample"},
        }
        res = save_template(payload, submit=0)
        doc = frappe.get_doc("WhatsApp Templates", res["name"])
        self.assertEqual(doc.header_type, "TEXT")
        self.assertEqual(doc.sample, "HeaderSample")

        # Media draft without file sample retains header_type
        payload["header"] = {"type": "IMAGE", "sample": ""}
        res2 = save_template(payload, submit=0, name=res["name"])
        doc2 = frappe.get_doc("WhatsApp Templates", res2["name"])
        self.assertEqual(doc2.header_type, "IMAGE")

    # `make_request` is imported into the page module's namespace, so the patch
    # must target that binding rather than frappe.integrations.utils.
    SYNC_REQUEST = "frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder.make_request"

    @patch(SYNC_REQUEST)
    def test_sync_single_template(self, mock_request):
        """Fix #8: Test targeted sync_template endpoint issues one GET and persists."""
        mock_request.return_value = {"id": "tmpl_id_sync", "status": "REJECTED"}
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import sync_template
        doc = self._make_template_without_hooks(template_name="test_tmpl_sync_single", status="PENDING")

        res = sync_template(doc.name)

        self.assertEqual(res["status"], "REJECTED")
        self.assertTrue(res["synced"])
        # One targeted GET against this template's id — not a global re-sync.
        self.assertEqual(mock_request.call_count, 1)
        args, _kwargs = mock_request.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn(doc.id, args[1])
        # Status is persisted, not just returned.
        self.assertEqual(frappe.db.get_value("WhatsApp Templates", doc.name, "status"), "REJECTED")

    @patch(SYNC_REQUEST)
    def test_sync_template_surfaces_failure(self, mock_request):
        """A Meta failure must raise, not report a successful no-op."""
        mock_request.side_effect = Exception("token expired")
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import sync_template
        doc = self._make_template_without_hooks(template_name="test_tmpl_sync_fail", status="PENDING")

        with self.assertRaises(frappe.ValidationError):
            sync_template(doc.name)

        # Status must be left untouched when the fetch failed.
        self.assertEqual(frappe.db.get_value("WhatsApp Templates", doc.name, "status"), "PENDING")

    @patch(SYNC_REQUEST)
    def test_sync_template_draft_is_noop(self, mock_request):
        """A draft that never reached Meta reports not-synced without calling out."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import sync_template
        doc = self._make_template_without_hooks(template_name="test_tmpl_sync_draft", id="", status="Pending")

        res = sync_template(doc.name)

        self.assertFalse(res["synced"])
        self.assertTrue(res["reason"])
        mock_request.assert_not_called()

    def test_parse_list_round_trip(self):
        """Fix #2: comma-bearing values survive serialize -> parse unchanged."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import parse_list, serialize_list

        for values in (
            ["$1,234.00", "Main Street, NY"],
            ["plain", "values"],
            ["[A]", "B"],
            ["a", "", "c"],
            ['He said "hi", ok'],
        ):
            stored = serialize_list(values)
            self.assertEqual(parse_list(stored), [v.strip() for v in values], f"round trip failed for {values}")

        # All-blank collapses to NULL so send-time treats it as unset.
        self.assertIsNone(serialize_list(["", ""]))

    def test_set_whatsapp_account_resolves_outgoing(self):
        """Fix #9: Test set_whatsapp_account resolves default outgoing account."""
        doc = self._make_template_without_hooks(template_name="test_tmpl_acct_outgoing", whatsapp_account="")
        doc.whatsapp_account = ""
        doc.set_whatsapp_account()
        self.assertEqual(doc.whatsapp_account, "Test WA Tmpl Account")

    def test_get_sample_record_single_doctype(self):
        """Fix #11: Test get_sample_record works with Single DocTypes without throwing SQL errors."""
        from frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder import get_sample_record
        res = get_sample_record("Website Settings", fieldnames=["title_prefix"])
        self.assertIn("record", res)
        self.assertEqual(res["record"], "Website Settings")

