# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request


class WhatsAppMessage(Document):
    """Send whats app messages."""

    def before_insert(self):
        """Send message."""
        if self.type == 'Outgoing':
            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(self.to),
                "type": "text",
                "text": {
                    "preview_url": True,
                    "body": self.message
                }
            }
            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
                frappe.throw(f"Failed to send message {str(e)}")

    def notify(self, data):
        """Notify."""
        settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
        token = settings.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }

        response = make_post_request(
            f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
            headers=headers, data=json.dumps(data)
        )

        frappe.get_doc({
            "doctype": "WhatsApp Notification Log",
            "template": "Text Message",
            "meta_data": response
        }).insert(ignore_permissions=True)

    def format_number(self, number):
        """Format number."""
        if number.startswith("+"):
            number = number[1:len(number)]

        return number
