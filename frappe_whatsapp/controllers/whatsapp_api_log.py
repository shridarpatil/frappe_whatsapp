
import frappe
from frappe.model.document import Document
from frappe import _

from myjhl.controllers.base_controller import BaseController
import requests
import json

@frappe.whitelist()
def ping():
	return "pong"

class WhatsAppAPIController(BaseController):

	""" antz: untuk create my wa api log"""
	def create_whatsapp_api_log(self, type, url, payload, headers, reference_doctype, reference_docname, method = "POST"):
		doc = frappe.get_doc({
			"url": url,
			"payload": payload,
			"type" : type,
			"headers" : headers,
			"status": "Pending",
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"method" : method,
			"doctype": "WhatsApp API Log"
		})
		doc.save(ignore_permissions=True)
		return doc
		

""" antz: dipakai di enqueue, karena server lemot untuk menerima request"""
@frappe.whitelist(allow_guest=False)
def send_data_to_whatsapp(url, body_data, headers, id_log, timeout = None, files = None,  raw_return = False) -> dict:
	try:

		# Kirim API
		response = requests.post(url=url, data=body_data, headers=headers, files = files,timeout= 50)
		
		# --------------
		print(str("---------"))
		print(str(vars(response)))
		# Handle response API
		if response.status_code not in [201, 200]:
			# Jika Error
			update_whatsapp_api_log(status = "Error", response= response, id_log= id_log)
			
			if raw_return:
				return response
			else:
				return {}
			
		else:
			# Jika berhasil
			update_whatsapp_api_log(status = "Success", response= response, id_log= id_log)

			if raw_return:
				return response
			else:
				response_message = ""
				try:
					if response.json():
						response_message = response.json()
				except:
					response_message = getattr(response, 'text') or None
				return response_message
		
	except:
		frappe.log_error(message = frappe.get_traceback(), title = (_("send_data_to_whatsapp: Gagal pada saat kirim API")))



""" antz: jika wa api error"""
def update_whatsapp_api_log(status, response, id_log):
	import json
	
	response_message = getattr(response, 'text') or str(json.loads(response.json())) 
	response_status_code = getattr(response, 'status_code') or "-"
	
	data = frappe.db.sql("""
	UPDATE `tabWhatsApp API Log`
	SET response_status_code = %(reponse_status_code)s,
		status = %(status)s,
		response_message = CONCAT( IFNULL(response_message, ""),%(response_message)s )

	WHERE
		name = %(name)s
	""",
	{
		"name" : id_log,
		"reponse_status_code" : response_status_code,
		"status" : str(status),
		"response_message" : str(response_message) + "\n\n ----------------------------------- \n\n"
	}, as_dict = 1)

	doc_whatsapp_api_log = frappe.get_doc("WhatsApp API Log", id_log)
	doc_whatsapp_api_log.save(ignore_permissions=True)
	
