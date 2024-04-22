# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import frappe

from frappe_whatsapp.controllers.whatsapp_api_log import WhatsAppAPIController
from frappe_whatsapp.controllers.whatsapp_api_log import send_data_to_whatsapp,update_whatsapp_api_log
from frappe.integrations.utils import make_post_request, make_request
from frappe.desk.form.utils import get_pdf_link
from frappe import _

import json

import os
import mimetypes
import requests


class WhatsAppTemplates(WhatsAppAPIController):
	"""Create whatsapp template."""

	# Function
	def get_absolute_path(self, file_name):
		if(file_name.startswith('/files/')):
			file_path = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}/public{file_name}'
		if(file_name.startswith('/private/')):
			file_path = f'{frappe.utils.get_bench_path()}/sites/{frappe.utils.get_site_base_path()[2:]}{file_name}'
		return file_path

	def get_all_info_file_header(self):
		""" untuk ambil info file dari sample header"""
		def get_file_size(file_path):
			return os.path.getsize(file_path)
		def get_mime_type(file_path):
			mime_type, _ = mimetypes.guess_type(file_path)
			return mime_type
		if self.header_type in ["DOCUMENT","IMAGE"]:
			self.size_file = 0
			file_path = self.get_absolute_path(self.sample_header)
			self.size_file = get_file_size(file_path)
			self.file_type = get_mime_type(file_path)


	# Start Hoooks ==========


	def autoname(self):
		if self.get("template_title"):
			self.template_name = self.template_title.lower().replace(' ', '_')

	def before_save(self):
		self.fill_language_code()
	
	def before_submit(self):
		"""Set template code."""
		self.template_name = self.template_name.lower().replace(' ', '_')
		self.language_code = frappe.db.get_value(
			"Language", self.language
		).replace('-', '_')

		self.get_settings()
		data = {
			"name": self.template_name,
			"language": self.language_code,
			"category": self.category,
			"components": []
		}

		body = {
			"type": "BODY",
			"text": self.template,
		}
		if self.sample_values:
			body.update({
				"example": {
					"body_text": [self.sample_values.split(',')]
				}
			})

		data['components'].append(body)
		if self.header_type:
			data['components'].append(self.get_header())

		# add footer
		if self.footer:
			data['components'].append({
				"type": "FOOTER",
				"text": self.footer
			})


		from frappe.utils.background_jobs import enqueue
		frappe.enqueue('frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.send_enqueue_data', name = self.get("name"),data=data)
		# try:

		# 	# Kirim Data =============

		# 	final_url = f"{self._url}/{self._version}/{self._business_id}/message_templates"
		# 	doc_log = self.create_whatsapp_api_log(type= "send_whatsapp_template", url = final_url, payload = json.dumps(data), headers = json.dumps(self._headers), reference_doctype= "WhatsApp Templates", reference_docname= self.get("template_name"), method = "POST")

		# 	response = send_data_to_whatsapp(url = final_url, body_data = json.dumps(data), headers = self._headers, id_log = doc_log.get("name"), timeout=15) or {}
		# 	if response.get("error"):
		# 		temp_error_message = response["error"].get("message") or "There are error while sending template to Meta."
		# 		if response["error"].get("message"):
		# 			frappe.throw(_(temp_error_message))
		# 	else:
		# 		# Olah Data =============
		# 		self.id = response.get('id')
		# 		self.status = response.get('status')
		# 		# frappe.db.set_value("WhatsApp Templates", self.name, "id", response.get('id'))
		# except Exception as e:
		# 	# res = frappe.flags.integration_request.json()['error']
		# 	# error_message = res.get('error_user_msg', res.get("message"))
		# 	# frappe.throw(
		# 	#     msg=str(e),
		# 	#     title = "err"
		# 	#     # title=res.get("error_user_title", "Error"),
		# 	# )
		# 	frappe.log_error(message = frappe.get_traceback(), title = ("wa_template: send_template"))

	


	# def on_update(self):
	#     """Update template to meta."""
	#     if self.get("id"):
	#         self.get_settings()
	#         data = {
	#             "components": []
	#         }

	#         body = {
	#             "type": "BODY",
	#             "text": self.template,
	#         }
	#         if self.sample_values:
	#             body.update({
	#                 "example": {
	#                     "body_text": [self.sample_values.split(',')]
	#                 }
	#             })
	#         data['components'].append(body)
	#         if self.header_type:
	#             data['components'].append(self.get_header())
	#         if self.footer:
	#             data['components'].append({
	#                 "type": "FOOTER",
	#                 "text": self.footer
	#             })
	#         try:
	#             # post template to meta for update
	#             response = make_post_request(
	#                 f"{self._url}/{self._version}/{self.id}",
	#                 headers=self._headers, data=json.dumps(data)
	#             )
	#         except Exception as e:
	#             frappe.log_error(message = frappe.get_traceback(), title = ("WA Template"))
	#             pass
	#             # # raise e
	#             # res = frappe.flags.integration_request.json()['error']
	#             # frappe.throw(
	#             #     msg=res.get('error_user_msg', res.get("message")),
	#             #     title=res.get("error_user_title", "Error"),
	#             # )


	def get_settings(self):
		"""Get whatsapp settings."""
		settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
		self._token = settings.get_password("token")
		self._url = settings.url
		self._version = settings.version
		self._business_id = settings.business_id
		self._application_id = settings.application_id

		self._headers = {
			"authorization": f"Bearer {self._token}",
			"content-type": "application/json"
		}

		self._oauth_headers = {
			'Authorization' : f'OAuth {self._token}',
			'file_offset': '0'
		}

	def on_trash(self):
		self.get_settings()
		url = f'{self._url}/{self._version}/{self._business_id}/message_templates?name={self.name}'
		try:
			make_request("DELETE", url, headers=self._headers)
		except Exception:
			res = frappe.flags.integration_request.json()['error']
			if res.get("error_user_title") == "Message Template Not Found":
				frappe.msgprint("Deleted locally", res.get("error_user_title", "Error"), alert=True)
			else:
				frappe.throw(
					msg=res.get("error_user_msg"),
					title=res.get("error_user_title", "Error"),
				)

	def get_header(self):
		"""Get header format."""
		header = {
			"type": "HEADER",
			"format": self.header_type
		}
		if self.header_type == "TEXT":
			# Untuk cek header text harus isi header
			if not self.get("header"):
				frappe.throw(_("Please fill field Header first"))
			header['text'] = self.header


		# Punya Frappe sendiri
		# elif self.header_type == "DOCUMENT":
		# 	if not self.sample:
		# 		key = frappe.get_doc(self.doctype, self.name).get_document_share_key()
		# 		link = get_pdf_link(self.doctype, self.name)
		# 		self.sample = f'{frappe.utils.get_url()}{link}&key={key}'
		# 	header.update({"example": {
		# 		"header_handle": [self.sample]
		# 	}})

		elif self.header_type == "IMAGE":
			if not self.sample_header:
				frappe.throw(_("Please fill with public url image first"))
			session_upload_header = self.create_session_whatsapp()
			upload_data_preview = self.send_file_preview(session_upload= session_upload_header)

			header.update({"example": {
				"header_handle": [upload_data_preview]
			}})

		return header
	
	# ================= Validate =================
	def validate_form_header_type(self):
		if self.header_type == "IMAGE":
				if not self.sample_header:
					frappe.throw(_("Please fill with public url image first"))
	
	# ================= Header Image =================

	def create_session_whatsapp(self) -> str:
		""" untuk membuat session whatsapp untuk create upload data"""
		# https://developers.facebook.com/docs/graph-api/guides/upload
		
		if self.header_type == 'IMAGE' or self.header_type == 'DOCUMENT':
			self.get_settings()
			self.get_all_info_file_header()
			temp_url = f'{self._url}/{self._version}/{self._application_id}/uploads'
			params = {
				'file_length': self.size_file,
				'file_type': self.file_type,
				'access_token': self._token
			}
			print("----------")
			print(params)
			# from requests.models import PreparedRequest
			req = requests.models.PreparedRequest()
			req.prepare_url(temp_url, params)
			final_url = req.url


			doc_log = self.create_whatsapp_api_log(type= "uploads_sample_template_session", url = final_url, payload = None, headers = None, reference_doctype= "WhatsApp Templates", reference_docname= self.get("template_name"), method = "POST")

			try:
				response = send_data_to_whatsapp(url = final_url, body_data = None, headers = None, id_log = doc_log.get("name")) or {}

				if response.get("id"):
					self.session_upload_header = response.get("id")

					return response.get("id")
				else:
					return ""
			except Exception as e:
				# res = frappe.flags.integration_request.json()['error']
				# error_message = res.get('error_user_msg', res.get("message"))
				# frappe.throw(
				#     msg=str(e),
				#     title = "err"
				#     # title=res.get("error_user_title", "Error"),
				# )
				frappe.log_error(message = frappe.get_traceback(), title = ("wa_template: create_session_whatsapp"))
				


			
				# frappe.db.set_value('Broadcast Template', self.name, 'upload_file_preview', json.dumps(res.json()))
				# frappe.db.commit()
				# if res.status_code != 200:
				# 	frappe.throw('Gagal Dapat ID File Preview')
				# else :
				# 	res_json = res.json()
				# 	id_file = res_json.get('id')
				# 	frappe.db.set_value('Broadcast Template', self.name, 'id_file_preview', res_json.get('id'))
				# 	frappe.db.commit()

				# url = f'{wa_settings.baseurl_meta}/{id_file}'
				# headers = { 'Authorization' : f'OAuth {wa_settings.token_wa}', 'file_offset': '0' }
				# # res_upload_file = requests.post(url=url, headers=headers)
				# file_path = self.get_absolute_path(self.file_example)
				# res_upload_file = None

				# with open(file_path, 'rb') as f:
				# 	files = { '@': f }
				# 	res_upload_file = requests.post(url = url, files=files, headers=headers)
				
				# frappe.db.set_value('Broadcast Template', self.name, 'upload_file_preview_2', json.dumps(res_upload_file.json()))
				# frappe.db.commit()

				# if res_upload_file.status_code != 200:
				# 	frappe.throw('Gagal Upload File')
				# else :
				# 	res_json = res_upload_file.json()
				# 	frappe.db.set_value('Broadcast Template', self.name, 'id_file_preview_2', res_json.get('h'))
				# 	frappe.db.commit()
						
	def send_file_preview(self, session_upload) -> str:
		""" untuk kirim preview """
		""" :param session_upload: Session diambil dari fungsi -> create_session_whatsapp """
		
		self.get_settings()
		final_url = f'{self._url}/{self._version}/{session_upload}'
		headers = self._oauth_headers

		# res_upload_file = requests.post(url=url, headers=headers)
		file_path = self.get_absolute_path(self.sample_header)
		res_upload_file = {}


		try:
			with open(file_path, 'rb') as f:
				files = { '@': f }

				# Send POST
				doc_log = self.create_whatsapp_api_log(type= "uploads_sample_template_data", url = final_url, payload = None, headers = json.dumps(headers), reference_doctype= "WhatsApp Templates", reference_docname= self.get("template_name"), method = "POST")
				res_upload_file = send_data_to_whatsapp(url = final_url, files = files, body_data = None, headers = headers, id_log = doc_log.get("name")) or {}

			if res_upload_file.get("h"):
				self.header_handle = res_upload_file.get("h")
				return self.header_handle
			# Tidak ketemu
			else:
				return ""
		except Exception as e:
			frappe.log_error(message = frappe.get_traceback(), title = ("wa_template: send_file_preview"))

		
		# frappe.db.set_value('Broadcast Template', self.name, 'upload_file_preview_2', json.dumps(res_upload_file.json()))
		# frappe.db.commit()

		# if res_upload_file.status_code != 200:
		# 	frappe.throw('Gagal Upload File')
		# else :
		# 	res_json = res_upload_file.json()
		# 	frappe.db.set_value('Broadcast Template', self.name, 'id_file_preview_2', res_json.get('h'))
		# 	frappe.db.commit()

	# ================= End of Hooks =================
	def fill_language_code(self):
		""" untuk mengisi language_code dari language"""
		if self.get("language"):
			self.language_code = frappe.db.get_value(
					"Language", self.get("language")
				).replace('-', '_')



@frappe.whitelist()
def fetch():
	"""Fetch templates from meta."""

	# get credentials
	settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
	token = settings.get_password("token")
	url = settings.url
	version = settings.version
	business_id = settings.business_id

	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}

	try:
		response = make_request(
			"GET",
			f"{url}/{version}/{business_id}/message_templates",
			headers=headers,
		)

		for template in response['data']:
			# set flag to insert or update
			flags = 1
			if frappe.db.exists("WhatsApp Templates", template['name']):
				doc = frappe.get_doc("WhatsApp Templates", template['name'])
			else:
				flags = 0
				doc = frappe.new_doc("WhatsApp Templates")
				doc.template_title = template['name']
				doc.template_name = template['name']
				
			doc.status = template['status']
			doc.language_code = template['language']
			doc.category = template['category']
			doc.id = template['id']
			doc.docstatus = 1

			# update components
			for component in template['components']:

				# update header
				if component['type'] == "HEADER":
					doc.header_type = component['format']

					# if format is text update sample text
					if component['format'] == 'TEXT':
						doc.header = component['text']
				# Update footer text
				elif component['type'] == 'FOOTER':
					doc.footer = component['text']

				# update template text
				elif component['type'] == 'BODY':
					doc.template = component['text']
					if component.get('example'):
						doc.sample_values = ','.join(component['example']['body_text'][0])

			# if document exists update else insert
			# used db_update and db_insert to ignore hooks
			if flags:
				doc.db_update()
			else:
				doc.db_insert()
			frappe.db.commit()

	except Exception as e:
		res = frappe.flags.integration_request.json()['error']
		error_message = res.get('error_user_msg', res.get("message"))
		frappe.throw(
			msg=error_message,
			title=res.get("error_user_title", "Error"),
		)

	return "Successfully fetched templates from meta"


# ================= Coba enqueu =================

def send_enqueue_data(name, data):
	try:
		# Kirim Data =============
		doc = frappe.get_doc("WhatsApp Templates", name)
		doc.get_settings()
		final_url = f"{doc._url}/{doc._version}/{doc._business_id}/message_templates"
		doc_log = doc.create_whatsapp_api_log(type= "send_whatsapp_template", url = final_url, payload = json.dumps(data), headers = json.dumps(doc._headers), reference_doctype= "WhatsApp Templates", reference_docname= doc.get("template_name"), method = "POST")

		response = send_data_to_whatsapp(url = final_url, body_data = json.dumps(data), headers = doc._headers, id_log = doc_log.get("name"), timeout=15) or {}
		if response.get("error"):
			temp_error_message = response["error"].get("message") or "There are error while sending template to Meta."
			if response["error"].get("message"):
				frappe.publish_realtime("msgprint", _(temp_error_message),user=frappe.session.user)
				# frappe.throw(_(temp_error_message))
		else:
			# Olah Data =============
			doc.id = response.get('id')
			doc.status = response.get('status')
			frappe.db.set_value("WhatsApp Templates", doc.name, {"id" : response.get('id'),
														 "status": response.get('status')})
			
			frappe.publish_realtime("msgprint", _("Template {name} has been updated.").format(name = doc.get("name")),user=frappe.session.user)
			

	except Exception as e:
		# res = frappe.flags.integration_request.json()['error']
		# error_message = res.get('error_user_msg', res.get("message"))
		# frappe.throw(
		#     msg=str(e),
		#     title = "err"
		#     # title=res.get("error_user_title", "Error"),
		# )
		frappe.log_error(message = frappe.get_traceback(), title = ("wa_template: send_template"))