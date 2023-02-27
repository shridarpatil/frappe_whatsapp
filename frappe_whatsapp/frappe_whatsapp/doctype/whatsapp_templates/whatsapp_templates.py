"""Create whatsapp template."""
# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request


class WhatsAppTemplates(Document):
    """Create whatsapp template."""

    def before_save(self):
        """Set template code."""
        self.template_name = self.template_name.lower().replace(' ', '_')
        self.language_code = frappe.db.get_value(
            "Language", self.language
        ).replace('-', '_')

    def after_insert(self):
        """Create Template on facebook dev."""
        self.get_settings()
        data = {
            "name": self.name,
            "language": self.language_code,
            "category": self.category,
            "components": [{
                "type": "BODY",
                "text": self.template
            }]
        }
        if self.header:
            data['components'].append({
                "type": "HEADER",
                "format": "TEXT",
                "text": self.header
            })
        if self.footer:
            data['components'].append({
                "type": "FOOTER",
                "text": self.footer
            })

        headers = {
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json"
        }

        try:
            response = make_post_request(
                f"{self._url}/{self._version}/{self._business_id}/message_templates",
                headers=headers, data=json.dumps(data)
            )
            self.id = response['id']
            frappe.db.set_value("WhatsApp Templates", self.name, "id", response['id'])
        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('error_user_msg', res.get("message"))
            frappe.msgprint(
                msg=error_message,
                title=res.get("error_user_title", "Error"),
                indicator="red"
            )
            raise e

    def get_settings(self):
        """Get whatsapp settings."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        self._token = settings.get_password("token")
        self._url = settings.url
        self._version = settings.version
        self._business_id = settings.business_id
