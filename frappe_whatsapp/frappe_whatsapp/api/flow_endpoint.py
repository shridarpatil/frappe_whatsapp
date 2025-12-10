# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

import json
import hashlib
import hmac
import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_flow_request():
    """
    Handle WhatsApp Flow data exchange requests.

    This endpoint receives requests from WhatsApp when a flow needs data
    or when a user completes a flow.

    Endpoint URL to configure in Meta:
    https://your-site.com/api/method/frappe_whatsapp.frappe_whatsapp.api.flow_endpoint.handle_flow_request
    """
    try:
        # Get request data
        if frappe.request.method == "GET":
            # Health check - WhatsApp pings this to verify endpoint
            return {"status": "ok"}

        # POST request - actual flow data
        data = frappe.request.get_json()

        if not data:
            frappe.throw(_("No data received"))

        # Log the request for debugging
        frappe.log_error(
            f"WhatsApp Flow Request:\n{json.dumps(data, indent=2)}",
            "WhatsApp Flow Endpoint"
        )

        # Get action type
        action = data.get("action")

        if action == "ping":
            # Health check
            return {
                "data": {
                    "status": "active"
                }
            }

        if action == "INIT":
            # Initial data request when flow opens
            flow_token = data.get("flow_token")
            screen_id = data.get("screen")

            return handle_init(flow_token, screen_id, data)

        if action == "data_exchange":
            # Data exchange during flow navigation
            return handle_data_exchange(data)

        if action == "BACK":
            # User pressed back button
            return handle_back(data)

        # Default response
        return {
            "data": {}
        }

    except Exception as e:
        frappe.log_error(f"Flow endpoint error: {str(e)}", "WhatsApp Flow Error")
        return {
            "data": {
                "error": str(e)
            }
        }


def handle_init(flow_token, screen_id, data):
    """Handle initial flow request."""
    # Return initial data for the first screen
    # This can be customized based on flow_token or other parameters

    return {
        "screen": screen_id or "INIT",
        "data": {}
    }


def handle_data_exchange(data):
    """Handle data exchange requests during flow."""
    flow_token = data.get("flow_token")
    screen = data.get("screen")
    form_data = data.get("data", {})

    # Process the form data
    # You can save it, validate it, or fetch additional data

    # Log flow data for processing
    if flow_token:
        save_flow_data(flow_token, screen, form_data)

    # Return next screen data or completion
    return {
        "data": {}
    }


def handle_back(data):
    """Handle back button press."""
    return {
        "data": {}
    }


def save_flow_data(flow_token, screen, form_data):
    """Save flow data for later processing."""
    try:
        # Create or update a record to store flow data
        existing = frappe.db.exists("WhatsApp Flow Data", {"flow_token": flow_token})

        if existing:
            doc = frappe.get_doc("WhatsApp Flow Data", existing)
            current_data = json.loads(doc.data or "{}")
            current_data.update(form_data)
            doc.data = json.dumps(current_data)
            doc.last_screen = screen
            doc.save(ignore_permissions=True)
        else:
            # If WhatsApp Flow Data doctype doesn't exist, just log
            frappe.log_error(
                f"Flow Token: {flow_token}\nScreen: {screen}\nData: {json.dumps(form_data)}",
                "WhatsApp Flow Data"
            )
    except Exception as e:
        frappe.log_error(f"save_flow_data error: {str(e)}")


def verify_signature(payload, signature, app_secret):
    """Verify the request signature from WhatsApp."""
    expected_signature = hmac.new(
        app_secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
