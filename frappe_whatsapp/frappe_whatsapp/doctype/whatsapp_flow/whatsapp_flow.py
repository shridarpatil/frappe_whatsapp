# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request, make_request


class WhatsAppFlow(Document):
    def before_save(self):
        """Generate flow JSON before saving."""
        self.flow_json = json.dumps(self.generate_flow_json(), indent=2)

    def validate(self):
        """Validate flow configuration."""
        self.validate_screens()

    def validate_screens(self):
        """Ensure at least one screen exists and has valid configuration."""
        if not self.screens:
            frappe.throw(_("At least one screen is required"))

        screen_ids = []
        terminal_count = 0

        for screen in self.screens:
            if screen.screen_id in screen_ids:
                frappe.throw(_("Duplicate screen ID: {0}").format(screen.screen_id))
            screen_ids.append(screen.screen_id)

            if screen.terminal:
                terminal_count += 1

        if terminal_count == 0:
            frappe.throw(_("At least one screen must be marked as terminal"))

    def generate_flow_json(self):
        """Generate WhatsApp Flow JSON from DocType configuration.

        Generates a client-only flow (no endpoint required).
        Data is collected and returned via webhook when flow completes.
        """
        flow = {
            "version": self.data_api_version or "6.0",
            "screens": []
        }

        # Build a map of which fields are passed to each screen from previous screens
        screen_incoming_data = self.build_screen_data_map()

        for screen in self.screens:
            screen_data = self.build_screen(screen, screen_incoming_data.get(screen.screen_id, {}))
            flow["screens"].append(screen_data)

        # Note: We intentionally do NOT include 'routing_model' or 'data_api_version'
        # This creates a client-only flow that doesn't require an endpoint
        # Data is returned via webhook (nfm_reply) when the flow completes

        return flow

    def build_screen_data_map(self):
        """Build a map of fields passed to each screen from previous screens.

        Returns:
            dict: {screen_id: {field_name: {"type": "string", "__example__": ""}}}
        """
        screen_data_map = {}
        accumulated_fields = {}  # Fields accumulated from all previous screens

        for i, screen in enumerate(self.screens):
            # Current screen receives all accumulated fields from previous screens
            if accumulated_fields:
                screen_data_map[screen.screen_id] = accumulated_fields.copy()

            # Add this screen's input fields to accumulated fields for next screens
            for field in self.fields:
                if field.screen != screen.screen_id:
                    continue
                if not field.enabled:
                    continue
                # Only input fields (not display components) are passed in payload
                if field.field_type not in [
                    "TextHeading", "TextSubheading", "TextBody",
                    "TextCaption", "Image", "EmbeddedLink", "Footer"
                ]:
                    accumulated_fields[field.field_name] = {
                        "type": "string",
                        "__example__": ""
                    }

        return screen_data_map

    def build_screen(self, screen, incoming_data=None):
        """Build a single screen definition."""
        screen_data = {
            "id": screen.screen_id,
            "title": screen.screen_title,
            "data": incoming_data or {},
            "layout": {
                "type": "SingleColumnLayout",
                "children": []
            }
        }

        if screen.terminal:
            screen_data["terminal"] = True
            screen_data["success"] = True

        if screen.refresh_on_back:
            screen_data["refresh_on_back"] = True

        # Build fields for this screen
        children = self.build_screen_fields(screen)
        screen_data["layout"]["children"] = children

        return screen_data

    def build_screen_fields(self, screen):
        """Build field components for a screen."""
        children = []
        has_footer = False

        # Get fields that belong to this screen from the fields table
        for field in self.fields:
            if field.screen != screen.screen_id:
                continue
            if not field.enabled:
                continue

            component = self.build_field_component(field, screen)
            if component:
                children.append(component)
                if field.field_type == "Footer":
                    has_footer = True

        # Always add a Footer if not present (required by WhatsApp)
        if not has_footer:
            footer_action = self.build_footer_action(None, screen)
            children.append({
                "type": "Footer",
                "label": "Continue" if not screen.terminal else "Complete",
                "on-click-action": footer_action
            })

        return children

    def build_field_component(self, field, screen):
        """Build a single field component."""
        field_type = field.field_type

        # Text display components (no input)
        if field_type in ["TextHeading", "TextSubheading", "TextBody", "TextCaption"]:
            return {
                "type": field_type,
                "text": field.label or ""
            }

        # Image component
        if field_type == "Image":
            component = {
                "type": "Image",
                "src": field.init_value or ""
            }
            if field.label:
                component["alt-text"] = field.label
            return component

        # Embedded link
        if field_type == "EmbeddedLink":
            return {
                "type": "EmbeddedLink",
                "text": field.label or "Link",
                "on-click-action": {
                    "name": "navigate",
                    "next": {"type": "screen", "name": field.init_value or ""}
                }
            }

        # Footer (submit button)
        if field_type == "Footer":
            action = self.build_footer_action(field, screen)
            return {
                "type": "Footer",
                "label": field.label or "Submit",
                "on-click-action": action
            }

        # Input components
        component = {
            "type": field_type,
            "name": field.field_name,
            "label": field.label or field.field_name
        }

        if field.required:
            component["required"] = True

        if field.helper_text:
            component["helper-text"] = field.helper_text

        if field.init_value:
            component["init-value"] = field.init_value

        # Text input specific
        if field_type in ["TextInput", "TextArea"]:
            if field.min_chars:
                component["min-chars"] = field.min_chars
            if field.max_chars:
                component["max-chars"] = field.max_chars
            if field.error_message:
                component["error-message"] = field.error_message

        # Options for dropdown/radio/checkbox
        if field_type in ["Dropdown", "RadioButtonsGroup", "CheckboxGroup"]:
            options = self.parse_options(field.options)
            if options:
                component["data-source"] = options

        # OptIn specific
        if field_type == "OptIn":
            component["label"] = field.label or "I agree"
            if field.required:
                component["required"] = True

        return component

    def build_footer_action(self, field, screen):
        """Build the action for a footer button."""
        if screen.terminal:
            # Complete the flow
            return {
                "name": "complete",
                "payload": self.build_payload(screen)
            }
        else:
            # Navigate to next screen
            next_screen = self.get_next_screen(screen)
            if next_screen:
                return {
                    "name": "navigate",
                    "next": {
                        "type": "screen",
                        "name": next_screen.screen_id
                    },
                    "payload": self.build_payload(screen)
                }
            else:
                return {
                    "name": "complete",
                    "payload": self.build_payload(screen)
                }

    def build_payload(self, screen):
        """Build payload with all field values up to and including this screen."""
        payload = {}

        # Include all fields from previous screens (passed via data) as data references
        found_current = False
        for s in self.screens:
            if s.screen_id == screen.screen_id:
                found_current = True
                # For current screen, use form references
                for field in self.fields:
                    if field.screen != s.screen_id:
                        continue
                    if field.enabled and field.field_type not in [
                        "TextHeading", "TextSubheading", "TextBody",
                        "TextCaption", "Image", "EmbeddedLink", "Footer"
                    ]:
                        payload[field.field_name] = "${form." + field.field_name + "}"
                break
            else:
                # For previous screens, use data references (already passed in)
                for field in self.fields:
                    if field.screen != s.screen_id:
                        continue
                    if field.enabled and field.field_type not in [
                        "TextHeading", "TextSubheading", "TextBody",
                        "TextCaption", "Image", "EmbeddedLink", "Footer"
                    ]:
                        payload[field.field_name] = "${data." + field.field_name + "}"

        return payload

    def get_next_screen(self, current_screen):
        """Get the next screen in sequence."""
        found_current = False
        for screen in self.screens:
            if found_current:
                return screen
            if screen.screen_id == current_screen.screen_id:
                found_current = True
        return None

    def parse_options(self, options_json):
        """Parse options JSON string to list."""
        if not options_json:
            return []
        try:
            options = json.loads(options_json)
            if isinstance(options, list):
                return options
            return []
        except json.JSONDecodeError:
            return []

    @frappe.whitelist()
    def create_on_whatsapp(self):
        """Create the flow on WhatsApp Business API."""
        if self.flow_id:
            frappe.throw(_("Flow already exists on WhatsApp. Use update instead."))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        # Create the flow
        url = f"{account.url}/{account.version}/{account.business_id}/flows"

        payload = {
            "name": self.flow_name,
            "categories": [self.category]
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = make_post_request(url, headers=headers, data=json.dumps(payload))
            self.flow_id = response.get("id")
            self.save()

            # Upload the flow JSON
            self.upload_flow_json()

            frappe.msgprint(_("Flow created successfully on WhatsApp"))

        except Exception as e:
            frappe.throw(_("Failed to create flow: {0}").format(str(e)))

    @frappe.whitelist()
    def upload_flow_json(self):
        """Upload flow JSON to WhatsApp."""
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}/assets"

        # Generate fresh flow JSON
        flow_json = self.generate_flow_json()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        files = {
            "file": ("flow.json", json.dumps(flow_json), "application/json"),
            "name": (None, "flow.json"),
            "asset_type": (None, "FLOW_JSON")
        }

        try:
            import requests
            response = requests.post(url, headers=headers, files=files)

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                # Also check for validation errors
                error_details = error_data.get("error", {}).get("error_user_msg", "")
                if error_details:
                    error_msg = f"{error_msg} - {error_details}"
                frappe.throw(_("Failed to upload flow JSON: {0}").format(error_msg))

            frappe.msgprint(_("Flow JSON uploaded successfully"))

        except requests.exceptions.RequestException as e:
            frappe.throw(_("Failed to upload flow JSON: {0}").format(str(e)))

    @frappe.whitelist()
    def publish_flow(self):
        """Publish the flow to make it available for use."""
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        if self.status == "Published":
            frappe.throw(_("Flow is already published"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}/publish"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            import requests
            response = requests.post(url, headers=headers)

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                frappe.throw(_("Failed to publish flow: {0}").format(error_msg))

            self.status = "Published"
            self.save()

            frappe.msgprint(_("Flow published successfully"))

        except Exception as e:
            frappe.throw(_("Failed to publish flow: {0}").format(str(e)))

    @frappe.whitelist()
    def deprecate_flow(self):
        """Deprecate the flow."""
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}/deprecate"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = make_post_request(url, headers=headers)
            self.status = "Deprecated"
            self.save()

            frappe.msgprint(_("Flow deprecated successfully"))

        except Exception as e:
            frappe.throw(_("Failed to deprecate flow: {0}").format(str(e)))

    @frappe.whitelist()
    def delete_from_whatsapp(self):
        """Delete the flow from WhatsApp."""
        if not self.flow_id:
            frappe.throw(_("Flow does not exist on WhatsApp"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            import requests
            response = requests.delete(url, headers=headers)
            response.raise_for_status()

            self.flow_id = None
            self.status = "Draft"
            self.save()

            frappe.msgprint(_("Flow deleted from WhatsApp"))

        except Exception as e:
            frappe.throw(_("Failed to delete flow: {0}").format(str(e)))

    @frappe.whitelist()
    def get_flow_preview(self):
        """Get the preview URL for the flow."""
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}?fields=preview.invalidate(false)"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            import requests
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            preview_url = data.get("preview", {}).get("preview_url")

            if preview_url:
                self.preview_url = preview_url
                self.save()
                return preview_url

            frappe.throw(_("Preview URL not available"))

        except Exception as e:
            frappe.throw(_("Failed to get preview: {0}").format(str(e)))

    @frappe.whitelist()
    def send_test(self, phone_number, message=None):
        """Send a test flow message to a phone number.

        Args:
            phone_number: Phone number to send to (must be a test number for draft flows)
            message: Optional message body
        """
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        # Create a WhatsApp Message to send the flow
        msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": phone_number,
            "content_type": "flow",
            "flow": self.name,
            "flow_cta": self.flow_cta or "Open Form",
            "message": message or f"Test: {self.flow_name}",
            "whatsapp_account": self.whatsapp_account
        })
        msg.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(
            _("Test flow sent to {0}").format(phone_number),
            indicator="green"
        )
        return msg.name

    @frappe.whitelist()
    def get_flow_status(self):
        """Get flow status and validation errors from WhatsApp."""
        if not self.flow_id:
            frappe.throw(_("Flow must be created on WhatsApp first"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}?fields=id,name,status,categories,validation_errors,json_version,data_api_version,data_channel_uri,preview,whatsapp_business_account"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            import requests
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Update local status
            if data.get("status"):
                self.status = data["status"].title()
                self.save()

            # Check for validation errors
            validation_errors = data.get("validation_errors", [])
            if validation_errors:
                error_messages = []
                for error in validation_errors:
                    error_messages.append(f"- {error.get('error', 'Unknown error')} at {error.get('error_type', 'unknown')}")
                frappe.msgprint(
                    _("Flow Validation Errors:\n{0}").format("\n".join(error_messages)),
                    title=_("Validation Errors"),
                    indicator="red"
                )
            else:
                frappe.msgprint(
                    _("Flow Status: {0}\nJSON Version: {1}").format(
                        data.get("status", "Unknown"),
                        data.get("json_version", "Unknown")
                    ),
                    title=_("Flow Status"),
                    indicator="green" if data.get("status") == "PUBLISHED" else "blue"
                )

            return data

        except Exception as e:
            frappe.throw(_("Failed to get flow status: {0}").format(str(e)))

    @frappe.whitelist()
    def sync_from_whatsapp(self):
        """Sync flow details from WhatsApp."""
        if not self.flow_id:
            frappe.throw(_("Flow ID is required to sync"))

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        # Get flow details
        url = f"{account.url}/{account.version}/{self.flow_id}?fields=id,name,status,categories,json_version,preview"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            import requests
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Update local fields
            if data.get("status"):
                self.status = data["status"].title()
            if data.get("categories"):
                self.category = data["categories"][0] if data["categories"] else "OTHER"
            if data.get("json_version"):
                self.data_api_version = data["json_version"]
            if data.get("preview", {}).get("preview_url"):
                self.preview_url = data["preview"]["preview_url"]

            # Try to get the flow JSON
            flow_json = self.fetch_flow_json()
            if flow_json:
                self.flow_json = json.dumps(flow_json, indent=2)

            self.save()
            frappe.msgprint(_("Flow synced successfully from WhatsApp"), indicator="green")

            return data

        except Exception as e:
            frappe.throw(_("Failed to sync flow: {0}").format(str(e)))

    def fetch_flow_json(self):
        """Fetch the flow JSON from WhatsApp."""
        if not self.flow_id:
            return None

        account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        token = account.get_password("token")

        url = f"{account.url}/{account.version}/{self.flow_id}/assets"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            import requests
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            assets = data.get("data", [])

            # Find the flow.json asset
            for asset in assets:
                if asset.get("name") == "flow.json":
                    # Download the asset
                    download_url = asset.get("download_url")
                    if download_url:
                        asset_response = requests.get(download_url, headers=headers)
                        if asset_response.status_code == 200:
                            return asset_response.json()

            return None

        except Exception as e:
            frappe.log_error(f"Failed to fetch flow JSON: {str(e)}")
            return None


@frappe.whitelist()
def get_whatsapp_flows(whatsapp_account):
    """Get list of all flows from WhatsApp Business Account.

    Args:
        whatsapp_account: Name of WhatsApp Account document

    Returns:
        List of flows from WhatsApp
    """
    account = frappe.get_doc("WhatsApp Account", whatsapp_account)
    token = account.get_password("token")

    url = f"{account.url}/{account.version}/{account.business_id}/flows?fields=id,name,status,categories"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        import requests
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        flows = data.get("data", [])

        # Check which flows already exist locally
        for flow in flows:
            existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow["id"]})
            flow["exists_locally"] = bool(existing)
            flow["local_name"] = existing if existing else None

        return flows

    except Exception as e:
        frappe.throw(_("Failed to fetch flows: {0}").format(str(e)))


@frappe.whitelist()
def import_flow_from_whatsapp(whatsapp_account, flow_id, flow_name=None):
    """Import a flow from WhatsApp into Frappe.

    Args:
        whatsapp_account: Name of WhatsApp Account document
        flow_id: WhatsApp Flow ID to import
        flow_name: Optional name for the flow (uses WhatsApp name if not provided)

    Returns:
        Name of created WhatsApp Flow document
    """
    # Check if flow already exists
    existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow_id})
    if existing:
        frappe.throw(_("Flow already exists: {0}").format(existing))

    account = frappe.get_doc("WhatsApp Account", whatsapp_account)
    token = account.get_password("token")

    # Get flow details
    url = f"{account.url}/{account.version}/{flow_id}?fields=id,name,status,categories,json_version,preview"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        import requests
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()

        # Create the flow document
        flow_doc = frappe.get_doc({
            "doctype": "WhatsApp Flow",
            "flow_name": flow_name or data.get("name", f"Imported Flow {flow_id}"),
            "whatsapp_account": whatsapp_account,
            "flow_id": flow_id,
            "status": data.get("status", "Draft").title(),
            "category": data["categories"][0] if data.get("categories") else "OTHER",
            "data_api_version": data.get("json_version", "6.0"),
            "preview_url": data.get("preview", {}).get("preview_url", "")
        })

        # Try to fetch and parse the flow JSON to create screens/fields
        flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)
        if flow_json:
            flow_doc.flow_json = json.dumps(flow_json, indent=2)
            parse_flow_json_to_screens(flow_doc, flow_json)

        # Skip validation since we're importing (may not have screens)
        flow_doc.flags.ignore_validate = True
        flow_doc.insert(ignore_permissions=True)

        frappe.db.commit()
        frappe.msgprint(_("Flow imported successfully: {0}").format(flow_doc.name), indicator="green")

        return flow_doc.name

    except Exception as e:
        frappe.throw(_("Failed to import flow: {0}").format(str(e)))


def fetch_flow_json_by_id(whatsapp_account, flow_id):
    """Fetch flow JSON by flow ID."""
    account = frappe.get_doc("WhatsApp Account", whatsapp_account)
    token = account.get_password("token")

    url = f"{account.url}/{account.version}/{flow_id}/assets"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        import requests
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        assets = data.get("data", [])

        for asset in assets:
            if asset.get("name") == "flow.json":
                download_url = asset.get("download_url")
                if download_url:
                    asset_response = requests.get(download_url, headers=headers)
                    if asset_response.status_code == 200:
                        return asset_response.json()

        return None

    except Exception as e:
        frappe.log_error(f"Failed to fetch flow JSON: {str(e)}")
        return None


@frappe.whitelist()
def sync_all_flows(whatsapp_account):
    """Sync all flows from WhatsApp Business Account.

    Imports new flows and updates existing ones.

    Args:
        whatsapp_account: Name of WhatsApp Account document

    Returns:
        Dict with counts: imported, updated, skipped
    """
    account = frappe.get_doc("WhatsApp Account", whatsapp_account)
    token = account.get_password("token")

    url = f"{account.url}/{account.version}/{account.business_id}/flows?fields=id,name,status,categories"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    result = {"imported": 0, "updated": 0, "skipped": 0}

    try:
        import requests
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        flows = data.get("data", [])

        for flow in flows:
            flow_id = flow.get("id")
            flow_name = flow.get("name")

            # Check if flow exists locally
            existing = frappe.db.exists("WhatsApp Flow", {"flow_id": flow_id})

            if existing:
                # Update existing flow
                try:
                    flow_doc = frappe.get_doc("WhatsApp Flow", existing)
                    flow_doc.status = flow.get("status", "Draft").title()
                    if flow.get("categories"):
                        flow_doc.category = flow["categories"][0]

                    # Try to fetch flow JSON and update screens/fields
                    flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)
                    if flow_json:
                        flow_doc.flow_json = json.dumps(flow_json, indent=2)
                        flow_doc.data_api_version = flow_json.get("version", "6.0")

                        # Clear existing screens and fields, then re-parse
                        flow_doc.screens = []
                        flow_doc.fields = []
                        parse_flow_json_to_screens(flow_doc, flow_json)

                    flow_doc.flags.ignore_validate = True
                    flow_doc.save(ignore_permissions=True)
                    result["updated"] += 1
                except Exception as e:
                    frappe.log_error(f"Failed to update flow {flow_id}: {str(e)}")
                    result["skipped"] += 1
            else:
                # Import new flow
                try:
                    flow_doc = frappe.get_doc({
                        "doctype": "WhatsApp Flow",
                        "flow_name": flow_name or f"Flow {flow_id}",
                        "whatsapp_account": whatsapp_account,
                        "flow_id": flow_id,
                        "status": flow.get("status", "Draft").title(),
                        "category": flow["categories"][0] if flow.get("categories") else "OTHER"
                    })

                    # Try to fetch and parse flow JSON
                    flow_json = fetch_flow_json_by_id(whatsapp_account, flow_id)
                    if flow_json:
                        flow_doc.flow_json = json.dumps(flow_json, indent=2)
                        flow_doc.data_api_version = flow_json.get("version", "6.0")
                        parse_flow_json_to_screens(flow_doc, flow_json)

                    flow_doc.flags.ignore_validate = True
                    flow_doc.insert(ignore_permissions=True)
                    result["imported"] += 1
                except Exception as e:
                    frappe.log_error(f"Failed to import flow {flow_id}: {str(e)}")
                    result["skipped"] += 1

        frappe.db.commit()
        return result

    except Exception as e:
        frappe.throw(_("Failed to sync flows: {0}").format(str(e)))


def parse_flow_json_to_screens(flow_doc, flow_json):
    """Parse flow JSON and create screens and fields in the document.

    Args:
        flow_doc: WhatsApp Flow document
        flow_json: Parsed flow JSON dict
    """
    screens = flow_json.get("screens", [])

    for screen_data in screens:
        # Add screen
        flow_doc.append("screens", {
            "screen_id": screen_data.get("id"),
            "screen_title": screen_data.get("title", ""),
            "terminal": 1 if screen_data.get("terminal") else 0,
            "refresh_on_back": 1 if screen_data.get("refresh_on_back") else 0
        })

        # Parse fields from layout
        layout = screen_data.get("layout", {})
        children = layout.get("children", [])

        for child in children:
            field_type = child.get("type")
            if not field_type:
                continue

            # Map WhatsApp field types to our field types
            field_data = {
                "screen": screen_data.get("id"),
                "field_type": field_type,
                "field_name": child.get("name", field_type.lower()),
                "label": child.get("label") or child.get("text", ""),
                "required": 1 if child.get("required") else 0,
                "enabled": 1,
                "helper_text": child.get("helper-text", ""),
                "init_value": child.get("init-value", ""),
                "min_chars": child.get("min-chars"),
                "max_chars": child.get("max-chars"),
                "error_message": child.get("error-message", "")
            }

            # Handle options for dropdowns
            if field_type in ["Dropdown", "RadioButtonsGroup", "CheckboxGroup"]:
                data_source = child.get("data-source", [])
                if data_source:
                    field_data["options"] = json.dumps(data_source)

            flow_doc.append("fields", field_data)
