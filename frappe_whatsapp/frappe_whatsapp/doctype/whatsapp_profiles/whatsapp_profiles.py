# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WhatsAppProfiles(Document):
    def validate(self):
        self.set_title()

    def set_title(self):
        self.title = " - ".join(filter(None, [self.profile_name, self.number]))
