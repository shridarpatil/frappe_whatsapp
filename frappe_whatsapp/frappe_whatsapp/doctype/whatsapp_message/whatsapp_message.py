# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request


class WhatsAppMessage(Document):
	"""Send whats app messages."""

	def before_save(self):
		self.create_masked_phone_number()

	def before_insert(self):
		if not self.get("using_system"):
			self.send_message_manual()
			self.send_message_template()

	def after_insert(self):
		# Commit karena harus ada supaya bisa di enqueue
		frappe.db.commit()
		if self.get("using_system"):
			self.send_whatsapp_enqueue()

	# ================= End of Hooks =================
	
	def create_masked_phone_number(self):
		if self.get("to"):
			self.masked_phone_number = get_masked(self.get("to"))

	# ================= Function =================
	
	def send_whatsapp_enqueue(self):
		from frappe.utils.background_jobs import enqueue
		frappe.enqueue('frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.send_whatsapp_enqueue_api', whatsapp_message=self.get("name"))

	def get_whatsapp_base_url(self) -> str:
		""" untuk ambil whatsapp base url"""
		settings = frappe.get_doc(
			"WhatsApp Settings", "WhatsApp Settings",
		)
		return settings.get("site_base_url") or ""


	# ================= End of Hooks =================

	def send_message_manual(self):
		"""Send message."""
		if self.type == 'Outgoing' and self.message_type != 'Template':
			if self.attach and not self.attach.startswith("http"):
				link = frappe.utils.get_url() + '/'+ self.attach
			else:
				link = self.attach

			data = {
				"messaging_product": "whatsapp",
				"to": self.format_number(self.to),
				"type": self.content_type
			}
			if self.content_type in ['document', 'image', 'video']:
				data[self.content_type.lower()] = {
					"link": link,
					"caption": self.message}
			elif self.content_type == "text":
				data["text"] = {
					"preview_url": True,
					"body": self.message
				}

			elif self.content_type == "audio":
				data["text"] = {
					"link": link
				}

			try:
				self.notify(data)
				self.status = "Success"
			except Exception as e:
				self.status = "Failed"
				frappe.throw(f"Failed to send message {str(e)}")

	def send_message_template(self):
		""" Send Message according template"""
		if self.type == 'Outgoing' and self.message_type == 'Template':
		
			wa_template_language, wa_template_id = frappe.get_value("WhatsApp Templates",self.get("whatsapp_template"), ["language_code", "template_name"])
			data = {
					"messaging_product": "whatsapp",
					"recipient_type": "individual",
					"to": self.format_number(self.to),
					"type": "template",
					"template": {
						"name": wa_template_id,
						"language": {
							"code": wa_template_language
						},
						"components" : []
					}
				}

			if self.get("template_values"):
				# Olah template values dulu
				list_value = self.get("template_values").split("\n")
				final_list_parameter = []
				for values in list_value:
					final_list_parameter.append({
						"type" : "text",
						"text" : values
					})
					

				data["template"]["components"].append(
					{
						"type": "body",
						"parameters" : final_list_parameter
					}
				)
			
			# Header Image
			if self.get("content_type") == "image":
				final_link_image = "{base_url}{attach}".format(base_url = self.get_whatsapp_base_url(), attach = self.get("attach"))
				# Buat parameters dulu dari link image
				param_image_header = {
					"type": "image",
					"image": {
						"link": final_link_image
					}
				}

				data["template"]["components"].append(
					{
						"type": "header",
						"parameters" : [param_image_header]
					}
				)

			try:
				self.send_template(data)
				self.status = "Success"
			except Exception as e:
				self.status = "Failed"
				frappe.throw(f"Failed to send message {str(e)}")
			

	# ================= Function =================


	def send_template(self,data):
		"""Send Template for template."""
		settings = frappe.get_doc(
			"WhatsApp Settings", "WhatsApp Settings",
		)
		token = settings.get_password("token")

		headers = {
			"authorization": f"Bearer {token}",
			"content-type": "application/json"
		}
		try:
			response = make_post_request(
				f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
				headers=headers, data=json.dumps(data)
			)
			self.message_id = response['messages'][0]['id']


		except Exception as e:
			res = frappe.flags.integration_request.json()['error']
			error_message = res.get('Error', res.get("message"))
			frappe.get_doc({
				"doctype": "WhatsApp Notification Log",
				"template": "Text Message",
				"meta_data": frappe.flags.integration_request.json()
			}).insert(ignore_permissions=True)
			frappe.log_error(message = frappe.get_traceback(), title = ("WhatsApp Message: Error When Sending Template"))
			frappe.throw(
				msg=error_message,
				title=res.get("error_user_title", "Error")
			)

	def notify(self, data):
		"""Notify."""
		settings = frappe.get_doc(
			"WhatsApp Settings", "WhatsApp Settings",
		)
		token = settings.get_password("token")

		headers = {
			"authorization": f"Bearer {token}",
			"content-type": "application/json"
		}
		try:
			response = make_post_request(
				f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
				headers=headers, data=json.dumps(data)
			)
			self.message_id = response['messages'][0]['id']

		except Exception as e:
			res = frappe.flags.integration_request.json()['error']
			error_message = res.get('Error', res.get("message"))
			frappe.get_doc({
				"doctype": "WhatsApp Notification Log",
				"template": "Text Message",
				"meta_data": frappe.flags.integration_request.json()
			}).insert(ignore_permissions=True)

			frappe.throw(
				msg=error_message,
				title=res.get("error_user_title", "Error")
			)

	def format_number(self, number):
		"""Format number."""
		if number.startswith("+"):
			number = number[1:len(number)]

		return number
	


# ================= Helper =================

@frappe.whitelist(allow_guest=False)
def send_whatsapp_enqueue_api(whatsapp_message):
	doc = frappe.get_doc("WhatsApp Message", whatsapp_message)
	doc.send_message_manual()
	doc.send_message_template()
	
	doc.save(ignore_permissions = True)
	

# ================= Helper Function =================


def get_masked(
	text: str
):
	""" ubah menjadi masked"""
	if not text:
		return text
		
	# ya
	jumlah_di_tampilkan_paling_belakang = 3
	masked_text = ((len(text) - jumlah_di_tampilkan_paling_belakang) * "*") + text[-jumlah_di_tampilkan_paling_belakang:]
	
	# response
	return masked_text
