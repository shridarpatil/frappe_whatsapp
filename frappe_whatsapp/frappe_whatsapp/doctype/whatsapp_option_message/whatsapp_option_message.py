# Copyright (c) 2024, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe import _

class WhatsAppOptionMessage(Document):
	def validate(self):
		try:
			data = json.loads(self.options)
		except ValueError as e:
			frappe.throw(_("Invalid JSON format"))

		if not isinstance(data, list):
			frappe.throw(_("The JSON field must be a list of objects"))

		if len(data) > 3:
			frappe.throw(_("The JSON array must not contain more than 3 objects"))

		seen_ids = set()
		seen_titles = set()

		for item in data:
			if not isinstance(item, dict):
				frappe.throw(_("Each item in the JSON array must be an object"))

			item_type = item.get('type')
			if item_type == 'reply':
				reply = item.get('reply', {})
				id_value = reply.get('id', '')
				title_value = reply.get('title', '')

				if not id_value or not title_value:
					frappe.throw(_("Each 'reply' object must contain 'id' and 'title' fields"))

				if len(id_value) > 20:
					frappe.throw(_("The 'id' field must not exceed 20 characters (Error at id: {0})").format(id_value))
				if len(title_value) > 20:
					frappe.throw(_("The 'title' field must not exceed 20 characters (Error at id: {0})").format(id_value))

				if id_value in seen_ids:
					frappe.throw(_("Duplicate 'id' found: {0}").format(id_value))
				if title_value in seen_titles:
					frappe.throw(_("Duplicate 'title' found: {0}").format(title_value))

				seen_ids.add(id_value)
				seen_titles.add(title_value)