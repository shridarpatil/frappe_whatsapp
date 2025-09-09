# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe_whatsapp.utils import format_number

class WhatsAppProfiles(Document):
    def validate(self):
        self.format_whatsapp_number()
        self.set_title()

    def format_whatsapp_number(self):
        if self.number:
            self.number = format_number(self.number)

    def set_title(self):
        self.title = " - ".join(filter(None, [self.profile_name, self.number])) or "Unnamed Profile"
