"""Create whatsapp template."""
# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WhatsAppTemplates(Document):
    """Create whatsapp template."""

    def before_save(self):
        """Set template code."""
        self.template_name = self.template_name.lower().replace(' ', '_')
        self.language_code = frappe.db.get_value(
            "Language", self.language
        ).replace('-', '_')
