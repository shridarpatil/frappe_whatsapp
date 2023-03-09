"""Notification."""

import json
import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import get_safe_globals, safe_exec
from frappe.integrations.utils import make_post_request


class WhatsAppNotification(Document):
    """Notification."""

    def validate(self):
        """Validate."""
        if self.notification_type == "DocType Event":
            fields = frappe.get_doc("DocType", self.reference_doctype).fields
            fields += frappe.get_all(
                "Custom Field",
                filters={"dt": self.reference_doctype},
                fields=["fieldname"]
            )
            if not any(field.fieldname == self.field_name for field in fields): # noqa
                frappe.throw(f"Field name {self.field_name} does not exists")

    def execute_method(self) -> dict:
        """Specific to API endpoint Server Scripts."""
        safe_exec(
            self.condition, get_safe_globals(), dict(doc=self)
        )
        language_code = frappe.db.get_value(
            "WhatsApp Templates", self.template,
            fieldname='language_code'
        )
        if language_code:
            for contact in self._contact_list:
                data = {
                    "messaging_product": "whatsapp",
                    "to": self.format_number(contact),
                    "type": "template",
                    "template": {
                        "name": self.template,
                        "language": {
                            "code": language_code
                        },
                        "components": []
                    }
                }

                self.notify(data)
        # return _globals.frappe.flags

    def execute_doc(self, doc: Document):
        """Specific to Document Event triggered Server Scripts."""
        if self.disabled:
            return

        doc_data = doc.as_dict()
        if self.condition:
            # check if condition satisfies
            if not frappe.safe_eval(
                self.condition, get_safe_globals(), dict(doc=doc_data)
            ):
                return

        language_code = frappe.db.get_value(
            "WhatsApp Templates", self.template,
            fieldname='language_code'
        )

        if language_code:
            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(doc_data[self.field_name]),
                "type": "template",
                "template": {
                    "name": self.template,
                    "language": {
                        "code": language_code
                    },
                    "components": []
                }
            }

            # Pass parameter values
            if self.fields:
                parameters = []
                for field in self.fields:
                    parameters.append({
                        "type": "text",
                        "text": doc_data[field.field_name]
                    })

                data['template']["components"] = [{
                    "type": "body",
                    "parameters": parameters
                }]

            self.notify(data)

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
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers, data=json.dumps(data)
            )
            frappe.get_doc({
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "message": str(data['template']),
                "to": data['to'],
                "message_type": "Template",
                "message_id": response['messages'][0]['id']
            }).save(ignore_permissions=True)
        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('Error', res.get("message"))
            frappe.msgprint(
                msg=error_message,
                title=res.get("error_user_title", "Error"),
                indicator="red"
            )
            raise e

        frappe.get_doc({
            "doctype": "WhatsApp Notification Log",
            "template": self.template,
            "meta_data": response
        }).insert(ignore_permissions=True)

    def on_trash(self):
        """On delete remove from schedule."""
        if self.notification_type == "Scheduler Event":
            frappe.delete_doc("Scheduled Job Type", self.name)

        frappe.cache().delete_value("whatsapp_notification_map")

    def after_insert(self):
        """After insert hook."""
        if self.notification_type == "Scheduler Event":
            method = f"frappe_whatsapp.utils.trigger_whatsapp_notifications_{self.event_frequency.lower().replace(' ', '_')}" # noqa
            job = frappe.get_doc(
                {
                    "doctype": "Scheduled Job Type",
                    "method": method,
                    "frequency": self.event_frequency
                }
            )

            job.insert()

    def format_number(self, number):
        """Format number."""
        if (number.startswith("+")):
            number = number[1:len(number)]

        return number