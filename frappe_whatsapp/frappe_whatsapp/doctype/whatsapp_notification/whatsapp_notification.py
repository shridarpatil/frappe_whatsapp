"""Notification."""

import json
import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import get_safe_globals
from frappe.integrations.utils import make_post_request


class WhatsAppNotification(Document):
    """Notification."""
    def validate(self):

        if not any(field.fieldname == self.field_name for field in frappe.get_doc("DocType", 'Vol Activity').fields):
            frappe.throw(f"Field name {self.field_name} does not exists")


    def execute_doc(self, doc: Document):
        """Specific to Document Event triggered Server Scripts."""
        if self.disabled:
            return

        if self.condition:
            if not frappe.safe_eval(
                self.condition, get_safe_globals(), dict(doc=doc.as_dict())
            ):
                return

        settings = frappe.db.get_value(
            "WhatsApp Settings", "WhatsApp Settings",
            fieldname=['token', 'url'], as_dict=True
        )
        headers = {
            "authorization": f"Bearer {settings.token}",
            "content-type": "application/json"
        }

        language_code = frappe.db.get_value(
            "WhatsApp Templates", self.template,
            fieldname='language_code'
        )

        if language_code:
            data = {
                "messaging_product": "whatsapp",
                "to": doc.__dict__[self.field_name],
                "type": "template",
                "template": {
                    "name": self.template,
                    "language": {
                        "code": language_code
                    }
                }
            }

            response = make_post_request(settings.url, headers=headers, data=json.dumps(data))
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": self.template,
                "meta_data": response
            }).insert(ignore_permissions=True)
            frappe.msgprint("Send WhatsAppNotification")
