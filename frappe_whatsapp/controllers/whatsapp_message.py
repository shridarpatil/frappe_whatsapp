
import frappe
from frappe.model.document import Document
from frappe import _

from grid.controllers.base_controller import BaseController

@frappe.whitelist()
def ping():
	return "pong"

class WhatsAppMessageController(BaseController):

	""" untuk ambil Booking Slot dan Booking Class sesuai tanggal yang diinputkan"""
	""" default: date hari ini"""
	def create_whatsapp_message(self, whatsapp_template, list_dict_wa_message, reference_doctype = "", reference_docname = ""):
		for item in list_dict_wa_message:
			doc = frappe.new_doc("WhatsApp Message")
			doc.update({
				"using_system" : 1,
				"type": "Outgoing",
				"to": item.get("to"),
				"message_type": "Template",
				"content_type": "text",
				"whatsapp_template": whatsapp_template,
				"template_values": item.get("parameter_values"),
				"reference_doctype" : reference_doctype,
				"reference_docname" : reference_docname,
				"user_doctype" : item.get("user_doctype") or "",
				"user_docname" : item.get("user_docname") or ""
			})
			doc.insert()
		
	
