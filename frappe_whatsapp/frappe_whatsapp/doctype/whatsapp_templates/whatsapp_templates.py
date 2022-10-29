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
                "text": "Bonus Tuesday starts now!"
            })
        if self.footer:
            data['components'].append({
                "type": "FOOTER",
                "text": "Not interested? Tap Stop promotions"
            })

        headers = {
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json"
        }

        response = make_post_request(
            f"{self._url}/{self._version}/{self._business_id}/message_templates",
            headers=headers, data=json.dumps(data)
        )
        self.id = response['id']
        frappe.db.set_value("WhatsApp Templates", self.name, "id", response['id'])

    def get_settings(self):
        """Get whatsapp settings."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        self._token = settings.get_password("token")
        self._url = settings.url
        self._version = settings.version
        self._business_id = settings.business_id
