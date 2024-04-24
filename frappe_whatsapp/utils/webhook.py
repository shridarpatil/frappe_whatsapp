"""Webhook."""
import frappe
import json
import requests
import time
from werkzeug.wrappers import Response
import frappe.utils


@frappe.whitelist(allow_guest=True)
def webhook():
	"""Meta webhook."""
	if frappe.request.method == "GET":
		masukkan_ke_file("whatsapp_get", frappe.local.form_dict or None)
		return get()
	return post()


def get():
	"""Get."""
	hub_challenge = frappe.form_dict.get("hub.challenge")
	webhook_verify_token = frappe.db.get_single_value(
		"WhatsApp Settings", "webhook_verify_token"
	)

	if frappe.form_dict.get("hub.verify_token") != webhook_verify_token:
		frappe.throw("Verify token does not match")

	return Response(hub_challenge, status=200)

def post():
	"""Post."""
	data = frappe.local.form_dict
	masukkan_ke_file("webhook_whatsapp", str(json.dumps(data)))
	process_whatsapp_notification_log(data = data)
	
	process_post_message(data = data)


def process_whatsapp_notification_log(data):
	""" untuk memindahkan data raw ke sistem"""

	final_dict = {
		"doctype": "WhatsApp Notification Log",
		"template": "Webhook",
		"meta_data": json.dumps(data)
	}

	# bisa olah data raw?
	try:
		if isinstance(data, dict) and data:
			changes = None
			try:
				changes = data["entry"][0]["changes"][0]
			except KeyError:
				changes = data["entry"]["changes"][0]
			# Changes data
			if changes.get("field") == "message_template_status_update":
				final_dict["type"] = "Template"
				
			elif changes.get("field") == "messages":
				final_dict["type"] = "Message"

				final_dict["phone_recipient"] = changes["value"]['statuses'][0]['recipient_id']
				final_dict["status_message"] = changes["value"]['statuses'][0]['status']

	except:
		frappe.log_error(message = frappe.get_traceback(), title = ("test wa: Error Title"))

	doc = frappe.get_doc(final_dict).insert(ignore_permissions=True)

	


def process_post_message(data):
	try:
		messages = []
		try:
			messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
		except KeyError:
			messages = data["entry"]["changes"][0]["value"].get("messages", [])

		if messages:
			for message in messages:
				message_type = message['type']
				is_reply = True if message.get('context') else False
				reply_to_message_id = message['context']['id'] if is_reply else None
				if message_type == 'text':
					frappe.get_doc({
						"doctype": "WhatsApp Message",
						"type": "Incoming",
						"from": message['from'],
						"message": message['text']['body'],
						"message_id": message['id'],
						"reply_to_message_id": reply_to_message_id,
						"is_reply": is_reply,
						"content_type":message_type
					}).insert(ignore_permissions=True)
				elif message_type == 'reaction':
					frappe.get_doc({
						"doctype": "WhatsApp Message",
						"type": "Incoming",
						"from": message['from'],
						"message": message['reaction']['emoji'],
						"reply_to_message_id": message['reaction']['message_id'],
						"message_id": message['id'],
						"content_type": "reaction"
					}).insert(ignore_permissions=True)
				elif message_type == 'interactive':
					frappe.get_doc({
						"doctype": "WhatsApp Message",
						"type": "Incoming",
						"from": message['from'],
						"message": message['interactive']['nfm_reply']['response_json'],
						"message_id": message['id'],
						"content_type": "flow"
					}).insert(ignore_permissions=True)
				elif message_type in ["image", "audio", "video", "document"]:
					settings = frappe.get_doc(
								"WhatsApp Settings", "WhatsApp Settings",
							)
					token = settings.get_password("token")
					url = f"{settings.url}/{settings.version}/"


					media_id = message[message_type]["id"]
					headers = {
						'Authorization': 'Bearer ' + token

					}
					response = requests.get(f'{url}{media_id}/', headers=headers)

					if response.status_code == 200:
						media_data = response.json()
						media_url = media_data.get("url")
						mime_type = media_data.get("mime_type")
						file_extension = mime_type.split('/')[1]

						media_response = requests.get(media_url, headers=headers)
						if media_response.status_code == 200:

							file_data = media_response.content
							file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"

							message_doc = frappe.get_doc({
								"doctype": "WhatsApp Message",
								"type": "Incoming",
								"from": message['from'],
								"message_id": message['id'],
								"reply_to_message_id": reply_to_message_id,
								"is_reply": is_reply,
								"message": message[message_type].get("caption",f"/files/{file_name}"),
								"content_type" : message_type
							}).insert(ignore_permissions=True)

							file = frappe.get_doc(
								{
									"doctype": "File",
									"file_name": file_name,
									"attached_to_doctype": "WhatsApp Message",
									"attached_to_name": message_doc.name,
									"content": file_data,
									"attached_to_field": "attach"
								}
							).save(ignore_permissions=True)


							message_doc.attach = file.file_url
							message_doc.save()

		else:
			changes = None
			try:
				changes = data["entry"][0]["changes"][0]
			except KeyError:
				changes = data["entry"]["changes"][0]
			update_status(changes)
		return
	except:
		frappe.log_error(message = frappe.get_traceback(), title = ("Whatsapp Webhook: Error Whatsapp Webhook"))

def update_status(data):
	"""Update status hook."""
	if data.get("field") == "message_template_status_update":
		update_template_status(data['value'])

	elif data.get("field") == "messages":
		update_message_status(data['value'])

def update_template_status(data):
	"""Update template status."""
	frappe.db.sql(
		"""UPDATE `tabWhatsApp Templates`
		SET status = %(event)s
		WHERE id = %(message_template_id)s""",
		data
	)

def update_message_status(data):
	"""Update message status."""
	id = data['statuses'][0]['id']
	status = data['statuses'][0]['status']
	conversation = data['statuses'][0].get('conversation', {}).get('id')
	name = frappe.db.get_value("WhatsApp Message", filters={"message_id": id})

	doc = frappe.get_doc("WhatsApp Message", name)
	doc.status = status
	if conversation:
		doc.conversation_id = conversation
	doc.save(ignore_permissions=True, ignore_version = True)



# ================= Helper =================

""" ambil data nya pakai fungsi get_data"""
def masukkan_ke_file(filename, data):
	f = open("{}.txt".format(filename), "a")
	f.write("{}\n".format(str(data)))
	f.close()

# == TEST ============================================
def test_process_whatsapp_notification_log(data):
	""" untuk memindahkan data raw ke sistem"""
	final_dict = {}

	# bisa olah data raw?
	if isinstance(data, dict) and data:
		changes = None
		try:
			changes = data["entry"][0]["changes"][0]
		except KeyError:
			changes = data["entry"]["changes"][0]
		# Changes data
		if changes.get("field") == "message_template_status_update":
			final_dict["type"] = "Template"
			
		elif changes.get("field") == "messages":
			final_dict["type"] = "Message"

			final_dict["phone_recipient"] = changes["value"]['statuses'][0]['recipient_id']
			final_dict["status_message"] = changes["value"]['statuses'][0]['recipient_id']
	print(final_dict)
