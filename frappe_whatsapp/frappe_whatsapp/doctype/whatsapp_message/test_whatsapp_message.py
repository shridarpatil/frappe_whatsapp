# Copyright (c) 2022, Shridhar Patil and Contributors
# See license.txt

import json
from unittest.mock import patch, MagicMock

import frappe
from frappe_whatsapp.testing import IntegrationTestCase


class TestWhatsAppMessage(IntegrationTestCase):
    """Tests for WhatsApp Message doctype."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_test_account()

    @classmethod
    def _ensure_test_account(cls):
        """Create a test WhatsApp Account if it doesn't exist."""
        if not frappe.db.exists("WhatsApp Account", "Test WA Msg Account"):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test WA Msg Account",
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "msg_test_phone_id",
                "business_id": "msg_test_business_id",
                "app_id": "msg_test_app_id",
                "webhook_verify_token": "msg_test_verify_token",
                "is_default_incoming": 1,
                "is_default_outgoing": 1,
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()

    def setUp(self):
        # Set password within each test's transaction scope
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("WhatsApp Account", "Test WA Msg Account", "test_token_123", "token")
        # Clear ALL defaults then set ours (db.set_value bypasses on_update hooks)
        frappe.db.sql("UPDATE `tabWhatsApp Account` SET is_default_outgoing=0, is_default_incoming=0")
        frappe.db.set_value("WhatsApp Account", "Test WA Msg Account", {
            "is_default_outgoing": 1,
            "is_default_incoming": 1,
        })

    def tearDown(self):
        for name in frappe.get_all("WhatsApp Message", filters={"to": ["like", "9199%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Message", name, force=True)
        for name in frappe.get_all("WhatsApp Message", filters={"from": ["like", "9199%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Message", name, force=True)
        for name in frappe.get_all("WhatsApp Profiles", filters={"number": ["like", "9199%"]}, pluck="name"):
            frappe.delete_doc("WhatsApp Profiles", name, force=True)
        frappe.db.commit()

    def test_incoming_message_creation(self):
        """Test creating an incoming WhatsApp message."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Incoming",
            "from": "919900112233",
            "message": "Hello World",
            "message_id": "wamid.test_incoming_1",
            "content_type": "text",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("WhatsApp Message", doc.name))
        self.assertEqual(doc.type, "Incoming")

    def test_set_whatsapp_account_default(self):
        """Test that whatsapp_account is auto-set to default when not provided."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Incoming",
            "from": "919900112244",
            "message": "Test default account",
            "message_id": "wamid.test_default_1",
            "content_type": "text",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.whatsapp_account, "Test WA Msg Account")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_text_message(self, mock_post):
        """Test sending an outgoing text message."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_outgoing_1"}],
            "contacts": [{"wa_id": "919900112255"}]
        }
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112255",
            "message": "Hello from test",
            "message_type": "Manual",
            "content_type": "text",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        self.assertEqual(doc.message_id, "wamid.test_outgoing_1")
        self.assertEqual(doc.status, "Success")

        # Verify the API was called with correct data
        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["messaging_product"], "whatsapp")
        self.assertEqual(sent_data["to"], "919900112255")
        self.assertEqual(sent_data["type"], "text")
        self.assertEqual(sent_data["text"]["body"], "Hello from test")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_text_message_with_plus_number(self, mock_post):
        """Test that + is stripped from phone numbers."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_plus_1"}],
        }
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "+919900112256",
            "message": "Test plus strip",
            "message_type": "Manual",
            "content_type": "text",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["to"], "919900112256")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_reply_message(self, mock_post):
        """Test sending a reply message includes context."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_reply_1"}],
        }
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112257",
            "message": "Reply test",
            "message_type": "Manual",
            "content_type": "text",
            "is_reply": 1,
            "reply_to_message_id": "wamid.original_msg_123",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertIn("context", sent_data)
        self.assertEqual(sent_data["context"]["message_id"], "wamid.original_msg_123")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_image_message(self, mock_post):
        """Test sending an image message."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_image_1"}],
        }
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112258",
            "message": "Image caption",
            "message_type": "Manual",
            "content_type": "image",
            "attach": "https://example.com/image.jpg",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["type"], "image")
        self.assertEqual(sent_data["image"]["link"], "https://example.com/image.jpg")
        self.assertEqual(sent_data["image"]["caption"], "Image caption")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_reaction_message(self, mock_post):
        """Test sending a reaction message."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_reaction_1"}],
        }
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": "919900112259",
            "message": "\U0001f44d",
            "message_type": "Manual",
            "content_type": "reaction",
            "reply_to_message_id": "wamid.react_to_msg",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["type"], "reaction")
        self.assertEqual(sent_data["reaction"]["emoji"], "\U0001f44d")
        self.assertEqual(sent_data["reaction"]["message_id"], "wamid.react_to_msg")

    def test_create_whatsapp_profile_on_insert(self):
        """Test that a WhatsApp Profile is created when a message is inserted."""
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Incoming",
            "from": "919900112260",
            "message": "Profile creation test",
            "message_id": "wamid.test_profile_create",
            "content_type": "text",
            "profile_name": "Test Profile User",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        self.assertTrue(
            frappe.db.exists("WhatsApp Profiles", {"number": "919900112260"})
        )

    def test_update_profile_name_on_update(self):
        """Test that profile name is updated when message profile_name changes."""
        # First create a profile
        profile = frappe.get_doc({
            "doctype": "WhatsApp Profiles",
            "profile_name": "Original Name",
            "number": "919900112261",
        })
        profile.insert(ignore_permissions=True)

        # Create incoming message with new profile name
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Incoming",
            "from": "919900112261",
            "message": "Update profile test",
            "message_id": "wamid.test_profile_update",
            "content_type": "text",
            "profile_name": "Updated Name",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        profile.reload()
        self.assertEqual(profile.profile_name, "Updated Name")

    def test_format_number_method(self):
        """Test the format_number instance method."""
        doc = frappe.new_doc("WhatsApp Message")
        self.assertEqual(doc.format_number("+919900112233"), "919900112233")
        self.assertEqual(doc.format_number("919900112233"), "919900112233")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_send_read_receipt(self, mock_post):
        """Test sending a read receipt."""
        mock_post.return_value = {"success": True}

        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Incoming",
            "from": "919900112262",
            "message": "Read receipt test",
            "message_id": "wamid.test_read_receipt",
            "content_type": "text",
            "whatsapp_account": "Test WA Msg Account",
        })
        doc.insert(ignore_permissions=True)

        result = doc.send_read_receipt()
        self.assertTrue(result)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        self.assertEqual(sent_data["status"], "read")
        self.assertEqual(sent_data["message_id"], "wamid.test_read_receipt")

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_outgoing_message_api_failure(self, mock_post):
        """Test that outgoing message handles API failure."""
        mock_post.side_effect = Exception("API Error")
        frappe.flags.integration_request = MagicMock()
        frappe.flags.integration_request.json.return_value = {
            "error": {"message": "Invalid phone number", "error_user_title": "Error"}
        }

        with self.assertRaises(frappe.ValidationError):
            doc = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "to": "919900112270",
                "message": "Fail test",
                "message_type": "Manual",
                "content_type": "text",
                "whatsapp_account": "Test WA Msg Account",
            })
            doc.insert(ignore_permissions=True)

    @patch("frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.make_post_request")
    def test_send_template_whitelisted(self, mock_post):
        """Test the send_template whitelisted function."""
        mock_post.return_value = {
            "messages": [{"id": "wamid.test_template_wl"}],
        }

        # First create a template (without hooks to avoid Meta API calls)
        if not frappe.db.exists("WhatsApp Templates", "test_msg_template-en"):
            frappe.get_doc({
                "doctype": "WhatsApp Templates",
                "template_name": "test_msg_template",
                "actual_name": "test_msg_template",
                "template": "Hello {{1}}",
                "category": "TRANSACTIONAL",
                "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
                "language_code": "en",
                "whatsapp_account": "Test WA Msg Account",
                "status": "APPROVED",
                "id": "test_template_id_123",
            }).db_insert()
            frappe.db.commit()

        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message import send_template
        send_template(
            to="919900112263",
            reference_doctype="User",
            reference_name="Administrator",
            template="test_msg_template-en"
        )

        self.assertTrue(
            frappe.db.exists("WhatsApp Message", {"to": "919900112263", "message_type": "Template"})
        )
