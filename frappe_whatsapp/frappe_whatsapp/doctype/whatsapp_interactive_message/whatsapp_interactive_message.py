# Copyright (c) 2024, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe import _

class WhatsAppInteractiveMessage(Document):
	def validate(self):
		try:
			data = json.loads(self.options)
		except ValueError as e:
			frappe.throw(_("Invalid JSON format"))

		if not isinstance(data, list):
			frappe.throw(_("The JSON field must be a list of objects"))

		if len(data) > 10:
			frappe.throw(_("The JSON array must not contain more than 10 objects"))

		seen_ids = set()
		seen_titles = set()

		for item in data:
			if not isinstance(item, dict):
				frappe.throw(_("Each item in the JSON array must be an object"))
			
			id_value = item.get('id', '')
			title_value = item.get('title', '')
			description_value = item.get('description', '')

			if len(id_value) > 24:
				frappe.throw(_("The 'id' field must not exceed 24 characters (Error at id: {0})").format(id_value))
			if len(title_value) > 24:
				frappe.throw(_("The 'title' field must not exceed 24 characters (Error at id: {0})").format(id_value))
			if len(description_value) > 72:
				frappe.throw(_("The 'description' field must not exceed 72 characters (Error at id: {0})").format(id_value))

			if id_value in seen_ids:
				frappe.throw(_("Duplicate 'id' found: {0}").format(id_value))
			if title_value in seen_titles:
				frappe.throw(_("Duplicate 'title' found: {0}").format(title_value))

			seen_ids.add(id_value)
			seen_titles.add(title_value)