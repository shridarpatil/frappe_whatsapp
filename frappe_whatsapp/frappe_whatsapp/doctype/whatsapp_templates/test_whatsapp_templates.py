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
        cls._ensure_test_account()
        cls._ensure_second_test_account()

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

    @classmethod
    def _ensure_second_test_account(cls):
        """A second active account on its own WhatsApp Business Account, for multi-account sync."""
        if not frappe.db.exists("WhatsApp Account", "Test WA Tmpl Account 2"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test WA Tmpl Account 2",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "tmpl_test_phone_id_2",
                "business_id": "tmpl_test_business_id_2",
                "app_id": "tmpl_test_app_id_2",
                "webhook_verify_token": "tmpl_test_verify_token_2",
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
        # Reset the request-scoped flag set by the Meta error-surfacing tests.
        frappe.flags.integration_request = None
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
        # Body has one variable, so give it one sample value (validate_sample_values).
        doc = self._make_template_without_hooks(template_name="test_tmpl_langcode", sample_values="John")
        doc.language_code = ""
        doc.language = frappe.db.get_value("Language", {"language_code": "en"}) or "en"
        doc.validate()
        self.assertTrue(len(doc.language_code) > 0)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_new_template_name_includes_language_code(self, mock_post):
        """A template saved from the form (language_code not filled yet) is named {template_name}-{language_code}."""
        mock_post.return_value = {"id": "tmpl_name_lang_id", "status": "PENDING"}

        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": "test_tmpl_name_lang",
            "template": "Hello",
            "category": "UTILITY",
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "whatsapp_account": "Test WA Tmpl Account",
        })
        doc.insert(ignore_permissions=True)

        self.assertEqual(doc.language_code, "en")
        self.assertEqual(doc.name, "test_tmpl_name_lang-en")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_same_template_name_in_two_languages(self, mock_post):
        """The same Template Label can be created once per language."""
        mock_post.return_value = {"id": "tmpl_two_lang_id", "status": "PENDING"}

        names = []
        for code in ("en", "hi"):
            doc = frappe.get_doc({
                "doctype": "WhatsApp Templates",
                "template_name": "test_tmpl_two_lang",
                "template": "Hello",
                "category": "UTILITY",
                "language": frappe.db.get_value("Language", {"language_code": code}) or code,
                "whatsapp_account": "Test WA Tmpl Account",
            })
            doc.insert(ignore_permissions=True)
            names.append(doc.name)

        self.assertEqual(names, ["test_tmpl_two_lang-en", "test_tmpl_two_lang-hi"])
        sent = [json.loads(c.kwargs["data"]) for c in mock_post.call_args_list]
        self.assertEqual([(d["name"], d["language"]) for d in sent], [("test_tmpl_two_lang", "en"), ("test_tmpl_two_lang", "hi")])

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

    def _templates_url(self, account_name):
        """message_templates endpoint fetch() calls for this account."""
        account = frappe.get_doc("WhatsApp Account", account_name)
        return f"{account.url}/{account.version}/{account.business_id}/message_templates"

    def _meta_template(self, name, language="en", body="Hello {{1}}", template_id=None):
        """One template in the shape Meta's message_templates API returns."""
        return {
            "name": name,
            "status": "APPROVED",
            "language": language,
            "category": "UTILITY",
            "id": template_id or f"meta_id_{name}_{language}",
            "components": [{"type": "BODY", "text": body}],
        }

    def _serve_meta_pages(self, mock_request, pages_by_url):
        """Answer each mocked GET with its page; other active accounts on the site get no templates."""
        mock_request.side_effect = lambda method, url, **kwargs: pages_by_url.get(url, {"data": []})

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_fetch_syncs_every_active_account(self, mock_request, mock_get_password):
        """fetch() syncs all active accounts, not only the first one."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch

        self._serve_meta_pages(mock_request, {
            self._templates_url("Test WA Tmpl Account"): {"data": [self._meta_template("test_tmpl_acct_one")]},
            self._templates_url("Test WA Tmpl Account 2"): {"data": [self._meta_template("test_tmpl_acct_two")]},
        })

        fetch()

        self.assertEqual(
            frappe.db.get_value("WhatsApp Templates", {"actual_name": "test_tmpl_acct_one"}, "whatsapp_account"),
            "Test WA Tmpl Account",
        )
        self.assertEqual(
            frappe.db.get_value("WhatsApp Templates", {"actual_name": "test_tmpl_acct_two"}, "whatsapp_account"),
            "Test WA Tmpl Account 2",
        )

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_fetch_follows_paging_next(self, mock_request, mock_get_password):
        """fetch() reads every page Meta returns, following paging.next until it is absent."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch

        first_page_url = self._templates_url("Test WA Tmpl Account")
        next_page_url = f"{first_page_url}?limit=1&after=cursor_page_2"
        self._serve_meta_pages(mock_request, {
            first_page_url: {
                "data": [self._meta_template("test_tmpl_page_one")],
                "paging": {"cursors": {"before": "cursor_page_1", "after": "cursor_page_2"}, "next": next_page_url},
            },
            next_page_url: {
                "data": [self._meta_template("test_tmpl_page_two")],
                "paging": {"cursors": {"before": "cursor_page_2", "after": "cursor_page_3"}},
            },
        })

        fetch()

        self.assertTrue(frappe.db.exists("WhatsApp Templates", {"actual_name": "test_tmpl_page_one"}))
        self.assertTrue(frappe.db.exists("WhatsApp Templates", {"actual_name": "test_tmpl_page_two"}))
        next_page_calls = [c for c in mock_request.call_args_list if c.args[1] == next_page_url]
        self.assertEqual(len(next_page_calls), 1)
        self.assertEqual(next_page_calls[0].kwargs["headers"]["authorization"], "Bearer mock_token")

    @patch("frappe.model.document.Document.get_password", return_value="mock_token")
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_request")
    def test_fetch_keeps_each_language_as_its_own_record(self, mock_request, mock_get_password):
        """Two languages of one Meta template stay two records, and a re-sync updates each in place."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import fetch

        english = self._meta_template("test_tmpl_multi_lang", language="en", body="Your order is ready")
        hindi = self._meta_template("test_tmpl_multi_lang", language="hi", body="Aapka order taiyaar hai")
        self._serve_meta_pages(mock_request, {
            self._templates_url("Test WA Tmpl Account"): {"data": [english, hindi]},
        })

        def synced_languages():
            return frappe.get_all(
                "WhatsApp Templates",
                filters={"actual_name": "test_tmpl_multi_lang"},
                fields=["name", "language_code", "id", "template"],
                order_by="language_code asc",
            )

        fetch()
        first_sync = synced_languages()
        self.assertEqual(
            [(t.name, t.language_code, t.id, t.template) for t in first_sync],
            [
                ("test_tmpl_multi_lang-en", "en", english["id"], "Your order is ready"),
                ("test_tmpl_multi_lang-hi", "hi", hindi["id"], "Aapka order taiyaar hai"),
            ],
        )

        hindi["components"][0]["text"] = "Aapka order bhej diya gaya hai"
        fetch()
        second_sync = synced_languages()
        self.assertEqual(
            [(t.name, t.template) for t in second_sync],
            [
                ("test_tmpl_multi_lang-en", "Your order is ready"),
                ("test_tmpl_multi_lang-hi", "Aapka order bhej diya gaya hai"),
            ],
        )

    def test_upsert_doc_without_hooks(self):
        """Test upsert_doc_without_hooks inserts and updates correctly."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import upsert_doc_without_hooks

        doc = self._make_template_without_hooks(template_name="test_tmpl_upsert")

        # Update template text
        doc.template = "Updated body text"
        upsert_doc_without_hooks(doc, "WhatsApp Button", "buttons")

        doc.reload()
        self.assertEqual(doc.template, "Updated body text")

    # ------------------------------------------------------------------
    # Open Point 1 — Sample Values validation
    # ------------------------------------------------------------------
    def _new_template_doc(self, **kwargs):
        """Build (not insert) a template doc with required fields defaulted."""
        data = {
            "doctype": "WhatsApp Templates",
            "template_name": kwargs.pop("template_name", "test_tmpl_op1"),
            "template": kwargs.pop("template", "Hello {{1}}"),
            "sample_values": kwargs.pop("sample_values", ""),
            # MARKETING is valid for both the base Select and leanerp_whatsapp's
            # custom_internal_category Select on v15.localhost.
            "category": kwargs.pop("category", "MARKETING"),
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": "Test WA Tmpl Account",
        }
        data.update(kwargs)
        return frappe.get_doc(data)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_sample_values_count_mismatch_blocks(self, mock_post):
        """3 variables but 2 values -> blocked, nothing sent to Meta."""
        doc = self._new_template_doc(
            template_name="test_tmpl_op1_count",
            template="Hi {{1}} {{2}} {{3}}",
            sample_values="a,b",
        )
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        mock_post.assert_not_called()

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_sample_values_newline_blocks(self, mock_post):
        """Values on separate lines -> blocked."""
        doc = self._new_template_doc(
            template_name="test_tmpl_op1_nl",
            template="Hi {{1}} {{2}} {{3}}",
            sample_values="a\nb\nc",
        )
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        mock_post.assert_not_called()

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_sample_values_gap_blocks(self, mock_post):
        """Only {{1}} and {{3}} (gap) -> blocked."""
        doc = self._new_template_doc(
            template_name="test_tmpl_op1_gap",
            template="Hi {{1}} {{3}}",
            sample_values="a,b",
        )
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        mock_post.assert_not_called()

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_sample_values_empty_but_vars_blocks(self, mock_post):
        """Variables present but Sample Values empty -> blocked (timesheet_reminder case)."""
        doc = self._new_template_doc(
            template_name="test_tmpl_op1_empty",
            template="Hi {{1}} {{2}}",
            sample_values="",
        )
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        mock_post.assert_not_called()

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_sample_values_trimmed_on_save(self, mock_post):
        """3 variables, 3 values with extra spaces -> saves, values trimmed."""
        mock_post.return_value = {"id": "op1_ok", "status": "PENDING"}
        doc = self._new_template_doc(
            template_name="test_tmpl_op1_trim",
            template="Hi {{1}} {{2}} {{3}}",
            sample_values=" a , b , c ",
        )
        doc.insert(ignore_permissions=True)
        self.assertTrue(mock_post.called)
        self.assertEqual(doc.sample_values, "a,b,c")

    # ------------------------------------------------------------------
    # SRO-2026-10-00227 — media header (DOCUMENT/IMAGE) crash
    # ------------------------------------------------------------------
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_media_header_without_sample_blocks(self, mock_post):
        """DOCUMENT header without a sample -> clear message, no crash, nothing sent."""
        doc = self._new_template_doc(
            template_name="test_tmpl_media_nosample",
            template="Your document is ready",
            header_type="DOCUMENT",
            sample="",
        )
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        mock_post.assert_not_called()

    def test_sample_not_reuploaded_when_unchanged(self):
        """Editing a media template without touching the sample does not re-upload."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import (
            WhatsAppTemplates,
        )

        doc = self._make_template_without_hooks(
            template_name="test_tmpl_media_gate",
            template="Your document is ready",
            category="MARKETING",
            header_type="DOCUMENT",
        )
        frappe.db.set_value(
            "WhatsApp Templates", doc.name,
            {"sample": "/files/doc.pdf", "header_media_handle": "H_OLD"},
        )
        doc.reload()

        with patch.object(WhatsAppTemplates, "get_session_id") as m_session, \
             patch.object(WhatsAppTemplates, "get_media_id") as m_media, \
             patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request") as mock_post:
            mock_post.return_value = {}
            doc.footer = "New footer"  # a Meta field changed, but the sample did not
            doc.save(ignore_permissions=True)
            m_session.assert_not_called()
            m_media.assert_not_called()
            self.assertTrue(mock_post.called)  # update ran, reusing the stored handle

    def test_sample_reuploaded_when_changed(self):
        """Changing the sample re-uploads it and refreshes the stored handle."""
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates import (
            WhatsAppTemplates,
        )

        doc = self._make_template_without_hooks(
            template_name="test_tmpl_media_change",
            template="Your document is ready",
            category="MARKETING",
            header_type="DOCUMENT",
        )
        frappe.db.set_value(
            "WhatsApp Templates", doc.name,
            {"sample": "/files/old.pdf", "header_media_handle": "H_OLD"},
        )
        doc.reload()

        def _fake_media(file):
            doc._media_id = "H_NEW"

        with patch.object(WhatsAppTemplates, "get_session_id") as m_session, \
             patch.object(WhatsAppTemplates, "get_media_id", side_effect=_fake_media) as m_media, \
             patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request") as mock_post:
            mock_post.return_value = {}
            doc.sample = "/files/new.pdf"
            doc.save(ignore_permissions=True)
            m_session.assert_called_once()
            m_media.assert_called_once()
        self.assertEqual(doc.header_media_handle, "H_NEW")

    # ------------------------------------------------------------------
    # SRO-2026-10-00228 — call Meta only on real changes + surface the error
    # ------------------------------------------------------------------
    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_no_meta_call_on_internal_field_change(self, mock_post):
        """Editing only an internal field (for_doctype) sends nothing to Meta."""
        doc = self._make_template_without_hooks(
            template_name="test_tmpl_internal",
            template="Order update",  # no variables
            category="MARKETING",
        )
        doc.for_doctype = "User"
        doc.save(ignore_permissions=True)
        mock_post.assert_not_called()

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_meta_call_on_body_change(self, mock_post):
        """Editing the body (a Meta-stored field) does call Meta."""
        mock_post.return_value = {}
        doc = self._make_template_without_hooks(
            template_name="test_tmpl_bodychg",
            template="Order update",
            category="MARKETING",
        )
        doc.template = "Order update v2"
        doc.save(ignore_permissions=True)
        self.assertTrue(mock_post.called)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_edit_error_shows_meta_message(self, mock_post):
        """On an edit error, Meta's real message is surfaced (not the raw 400)."""
        from requests.exceptions import HTTPError

        doc = self._make_template_without_hooks(
            template_name="test_tmpl_err",
            template="Order update",
            category="MARKETING",
        )
        resp = MagicMock()
        resp.json.return_value = {
            "error": {"error_user_msg": "Real Meta reason", "error_user_title": "Oops"}
        }
        frappe.flags.integration_request = resp
        mock_post.side_effect = HTTPError("400 Client Error: Bad Request")

        doc.template = "Order update v2"
        with self.assertRaises(frappe.ValidationError) as cm:
            doc.save(ignore_permissions=True)
        self.assertIn("Real Meta reason", str(cm.exception))

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request")
    def test_network_error_shows_readable_message(self, mock_post):
        """A connection error gives a readable message, not 'NoneType ... json'."""
        from requests.exceptions import ConnectionError as ReqConnectionError

        doc = self._make_template_without_hooks(
            template_name="test_tmpl_net",
            template="Order update",
            category="MARKETING",
        )
        frappe.flags.integration_request = None
        mock_post.side_effect = ReqConnectionError("Failed to establish a new connection")

        doc.template = "Order update v2"
        with self.assertRaises(frappe.ValidationError) as cm:
            doc.save(ignore_permissions=True)
        self.assertIn("Could not reach Meta", str(cm.exception))
