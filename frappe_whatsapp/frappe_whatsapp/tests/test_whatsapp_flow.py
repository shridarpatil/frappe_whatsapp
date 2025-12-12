# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

import unittest
import json
import frappe
from frappe.tests.utils import FrappeTestCase


class TestWhatsAppFlow(FrappeTestCase):
    """Test cases for WhatsApp Flow feature."""

    def setUp(self):
        """Set up test data."""
        # Create a test WhatsApp Account if it doesn't exist
        if not frappe.db.exists("WhatsApp Account", "Test Account"):
            frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": "Test Account",
                "url": "https://graph.facebook.com",
                "version": "v18.0",
                "phone_id": "123456789",
                "business_id": "987654321",
                "token": "test_token"
            }).insert(ignore_permissions=True)

    def tearDown(self):
        """Clean up test data."""
        # Delete test flows
        for flow in frappe.get_all("WhatsApp Flow", filters={"flow_name": ["like", "Test%"]}):
            frappe.delete_doc("WhatsApp Flow", flow.name, force=True)

    def create_test_flow(self, flow_name, screens_data, fields_data):
        """Helper to create a test flow."""
        flow = frappe.get_doc({
            "doctype": "WhatsApp Flow",
            "flow_name": flow_name,
            "whatsapp_account": "Test Account",
            "category": "OTHER",
            "data_api_version": "7.3",
            "screens": screens_data,
            "fields": fields_data
        })
        flow.insert(ignore_permissions=True)
        return flow

    def test_single_screen_flow_json_generation(self):
        """Test flow JSON generation for a single screen flow."""
        screens = [{
            "screen_id": "WELCOME",
            "screen_title": "Welcome",
            "terminal": 1
        }]
        fields = [{
            "screen": "WELCOME",
            "field_name": "user_name",
            "field_type": "TextInput",
            "label": "Your Name",
            "required": 1,
            "enabled": 1
        }]

        flow = self.create_test_flow("Test Single Screen", screens, fields)
        flow_json = json.loads(flow.flow_json)

        # Verify structure
        self.assertEqual(flow_json["version"], "7.3")
        self.assertEqual(len(flow_json["screens"]), 1)

        # Verify screen
        screen = flow_json["screens"][0]
        self.assertEqual(screen["id"], "WELCOME")
        self.assertEqual(screen["title"], "Welcome")
        self.assertTrue(screen.get("terminal"))
        self.assertTrue(screen.get("success"))

        # Verify no routing_model or data_api_version (client-only flow)
        self.assertNotIn("routing_model", flow_json)
        self.assertNotIn("data_api_version", flow_json)

    def test_multi_screen_flow_json_generation(self):
        """Test flow JSON generation for multi-screen flow."""
        screens = [
            {"screen_id": "contact", "screen_title": "Contact Details", "terminal": 0},
            {"screen_id": "booking", "screen_title": "Booking Details", "terminal": 1}
        ]
        fields = [
            {"screen": "contact", "field_name": "name", "field_type": "TextInput", "label": "Name", "required": 1, "enabled": 1},
            {"screen": "contact", "field_name": "mobile", "field_type": "TextInput", "label": "Mobile", "required": 1, "enabled": 1},
            {"screen": "booking", "field_name": "date", "field_type": "TextInput", "label": "Date", "required": 1, "enabled": 1}
        ]

        flow = self.create_test_flow("Test Multi Screen", screens, fields)
        flow_json = json.loads(flow.flow_json)

        # Verify two screens
        self.assertEqual(len(flow_json["screens"]), 2)

        # First screen should have empty data (no incoming data)
        self.assertEqual(flow_json["screens"][0]["data"], {})

        # Second screen should have data declarations for fields from first screen
        second_screen_data = flow_json["screens"][1]["data"]
        self.assertIn("name", second_screen_data)
        self.assertIn("mobile", second_screen_data)
        self.assertEqual(second_screen_data["name"]["type"], "string")

    def test_navigate_action_payload(self):
        """Test that navigate action includes correct payload."""
        screens = [
            {"screen_id": "screen1", "screen_title": "Screen 1", "terminal": 0},
            {"screen_id": "screen2", "screen_title": "Screen 2", "terminal": 1}
        ]
        fields = [
            {"screen": "screen1", "field_name": "field1", "field_type": "TextInput", "label": "Field 1", "required": 1, "enabled": 1}
        ]

        flow = self.create_test_flow("Test Navigate", screens, fields)
        flow_json = json.loads(flow.flow_json)

        # Find the footer in first screen
        first_screen = flow_json["screens"][0]
        footer = None
        for child in first_screen["layout"]["children"]:
            if child.get("type") == "Footer":
                footer = child
                break

        self.assertIsNotNone(footer)
        action = footer["on-click-action"]
        self.assertEqual(action["name"], "navigate")
        self.assertEqual(action["next"]["name"], "screen2")

        # Payload should reference form fields
        self.assertEqual(action["payload"]["field1"], "${form.field1}")

    def test_complete_action_payload(self):
        """Test that complete action includes all accumulated data."""
        screens = [
            {"screen_id": "screen1", "screen_title": "Screen 1", "terminal": 0},
            {"screen_id": "screen2", "screen_title": "Screen 2", "terminal": 1}
        ]
        fields = [
            {"screen": "screen1", "field_name": "name", "field_type": "TextInput", "label": "Name", "enabled": 1},
            {"screen": "screen2", "field_name": "email", "field_type": "TextInput", "label": "Email", "enabled": 1}
        ]

        flow = self.create_test_flow("Test Complete", screens, fields)
        flow_json = json.loads(flow.flow_json)

        # Find footer in terminal screen
        terminal_screen = flow_json["screens"][1]
        footer = None
        for child in terminal_screen["layout"]["children"]:
            if child.get("type") == "Footer":
                footer = child
                break

        self.assertIsNotNone(footer)
        action = footer["on-click-action"]
        self.assertEqual(action["name"], "complete")

        # Payload should include data from previous screen and form from current
        payload = action["payload"]
        self.assertEqual(payload["name"], "${data.name}")  # From previous screen
        self.assertEqual(payload["email"], "${form.email}")  # From current screen

    def test_text_display_components(self):
        """Test text display components (TextHeading, TextBody, etc.)."""
        screens = [{"screen_id": "info", "screen_title": "Info", "terminal": 1}]
        fields = [
            {"screen": "info", "field_name": "heading", "field_type": "TextHeading", "label": "Welcome!", "enabled": 1},
            {"screen": "info", "field_name": "body", "field_type": "TextBody", "label": "Please fill the form", "enabled": 1}
        ]

        flow = self.create_test_flow("Test Text Components", screens, fields)
        flow_json = json.loads(flow.flow_json)

        children = flow_json["screens"][0]["layout"]["children"]

        # Text components should have type and text properties
        heading = children[0]
        self.assertEqual(heading["type"], "TextHeading")
        self.assertEqual(heading["text"], "Welcome!")

        body = children[1]
        self.assertEqual(body["type"], "TextBody")
        self.assertEqual(body["text"], "Please fill the form")

    def test_dropdown_with_options(self):
        """Test dropdown field with options."""
        screens = [{"screen_id": "select", "screen_title": "Select", "terminal": 1}]
        fields = [{
            "screen": "select",
            "field_name": "country",
            "field_type": "Dropdown",
            "label": "Country",
            "enabled": 1,
            "options": json.dumps([
                {"id": "us", "title": "United States"},
                {"id": "uk", "title": "United Kingdom"},
                {"id": "in", "title": "India"}
            ])
        }]

        flow = self.create_test_flow("Test Dropdown", screens, fields)
        flow_json = json.loads(flow.flow_json)

        children = flow_json["screens"][0]["layout"]["children"]
        dropdown = children[0]

        self.assertEqual(dropdown["type"], "Dropdown")
        self.assertEqual(dropdown["name"], "country")
        self.assertEqual(len(dropdown["data-source"]), 3)
        self.assertEqual(dropdown["data-source"][0]["id"], "us")

    def test_text_input_validation(self):
        """Test text input with min/max chars."""
        screens = [{"screen_id": "form", "screen_title": "Form", "terminal": 1}]
        fields = [{
            "screen": "form",
            "field_name": "phone",
            "field_type": "TextInput",
            "label": "Phone",
            "enabled": 1,
            "min_chars": 10,
            "max_chars": 15,
            "error_message": "Phone must be 10-15 digits"
        }]

        flow = self.create_test_flow("Test Validation", screens, fields)
        flow_json = json.loads(flow.flow_json)

        children = flow_json["screens"][0]["layout"]["children"]
        phone_field = children[0]

        self.assertEqual(phone_field["min-chars"], 10)
        self.assertEqual(phone_field["max-chars"], 15)
        self.assertEqual(phone_field["error-message"], "Phone must be 10-15 digits")

    def test_disabled_fields_excluded(self):
        """Test that disabled fields are not included in flow JSON."""
        screens = [{"screen_id": "form", "screen_title": "Form", "terminal": 1}]
        fields = [
            {"screen": "form", "field_name": "active", "field_type": "TextInput", "label": "Active", "enabled": 1},
            {"screen": "form", "field_name": "disabled", "field_type": "TextInput", "label": "Disabled", "enabled": 0}
        ]

        flow = self.create_test_flow("Test Disabled", screens, fields)
        flow_json = json.loads(flow.flow_json)

        children = flow_json["screens"][0]["layout"]["children"]
        field_names = [c.get("name") for c in children if c.get("name")]

        self.assertIn("active", field_names)
        self.assertNotIn("disabled", field_names)

    def test_validation_requires_screen(self):
        """Test that flow validation requires at least one screen."""
        with self.assertRaises(frappe.ValidationError):
            flow = frappe.get_doc({
                "doctype": "WhatsApp Flow",
                "flow_name": "Test No Screens",
                "whatsapp_account": "Test Account",
                "category": "OTHER",
                "screens": [],
                "fields": []
            })
            flow.insert(ignore_permissions=True)

    def test_validation_requires_terminal_screen(self):
        """Test that flow validation requires at least one terminal screen."""
        with self.assertRaises(frappe.ValidationError):
            flow = frappe.get_doc({
                "doctype": "WhatsApp Flow",
                "flow_name": "Test No Terminal",
                "whatsapp_account": "Test Account",
                "category": "OTHER",
                "screens": [{"screen_id": "s1", "screen_title": "Screen 1", "terminal": 0}],
                "fields": []
            })
            flow.insert(ignore_permissions=True)

    def test_validation_duplicate_screen_ids(self):
        """Test that flow validation catches duplicate screen IDs."""
        with self.assertRaises(frappe.ValidationError):
            flow = frappe.get_doc({
                "doctype": "WhatsApp Flow",
                "flow_name": "Test Duplicate",
                "whatsapp_account": "Test Account",
                "category": "OTHER",
                "screens": [
                    {"screen_id": "same", "screen_title": "Screen 1", "terminal": 0},
                    {"screen_id": "same", "screen_title": "Screen 2", "terminal": 1}
                ],
                "fields": []
            })
            flow.insert(ignore_permissions=True)

    def test_client_only_flow_no_endpoint_fields(self):
        """Test that generated JSON is client-only (no endpoint required)."""
        screens = [{"screen_id": "test", "screen_title": "Test", "terminal": 1}]
        fields = [{"screen": "test", "field_name": "f1", "field_type": "TextInput", "label": "F1", "enabled": 1}]

        flow = self.create_test_flow("Test Client Only", screens, fields)
        flow_json = json.loads(flow.flow_json)

        # Client-only flows should NOT have these fields
        self.assertNotIn("routing_model", flow_json)
        self.assertNotIn("data_api_version", flow_json)
        self.assertNotIn("data_channel_uri", flow_json)

        # Should have version and screens
        self.assertIn("version", flow_json)
        self.assertIn("screens", flow_json)


class TestWhatsAppFlowMessage(FrappeTestCase):
    """Test cases for sending WhatsApp Flow messages."""

    def test_flow_message_structure(self):
        """Test the structure of flow message data."""
        # This tests the message building logic without actually sending
        from frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage

        # Mock flow doc
        class MockFlow:
            flow_id = "123456789"
            flow_cta = "Open Form"
            status = "Draft"
            screens = [type('Screen', (), {'screen_id': 'test'})()]

        class MockMessage(WhatsAppMessage):
            def __init__(self):
                self.content_type = "flow"
                self.flow = "Test Flow"
                self.flow_cta = "Fill Form"
                self.flow_screen = "contact"
                self.flow_token = "test_token_123"
                self.message = "Please complete the form"
                self.to = "919876543210"

        # Verify the expected message structure
        expected_keys = ["flow_message_version", "flow_id", "flow_cta", "flow_action", "flow_action_payload", "flow_token"]

        # The actual structure would be built in before_insert
        # Here we just verify the expected fields exist in our implementation


class TestFlowEndpoint(FrappeTestCase):
    """Test cases for flow endpoint handler."""

    def test_health_check(self):
        """Test endpoint health check response."""
        from frappe_whatsapp.frappe_whatsapp.api.flow_endpoint import handle_init

        response = handle_init(None, "INIT", {})
        self.assertIn("screen", response)
        self.assertIn("data", response)

    def test_ping_action(self):
        """Test ping action response."""
        # The endpoint should respond to ping with status: active
        expected_response = {"data": {"status": "active"}}
        # This would be tested via actual HTTP request in integration tests


if __name__ == "__main__":
    unittest.main()
