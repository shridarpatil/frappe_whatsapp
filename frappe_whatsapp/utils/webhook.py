"""Webhook."""
import frappe
import json
import requests
import time
from frappe.utils import get_site_name
from werkzeug.wrappers import Response
import frappe.utils

settings = frappe.get_doc(
			"WhatsApp Settings", "WhatsApp Settings",
		)
token = settings.get_password("token")
url = f"{settings.url}/{settings.version}/"
bench_location = frappe.utils.get_bench_path()
site_name = get_site_name(frappe.local.request.host)

@frappe.whitelist(allow_guest=True)
def webhook():
	"""Meta webhook."""
	if frappe.request.method == "GET":
		return get()
	return post()


def get():
	"""Get."""
	hub_challenge = frappe.form_dict.get("hub.challenge")
	webhook_verify_token = frappe.db.get_single_value(
		"Whatsapp Settings", "webhook_verify_token"
	)

	if frappe.form_dict.get("hub.verify_token") != webhook_verify_token:
		frappe.throw("Verify token does not match")

	return Response(hub_challenge, status=200)

def post():
	"""Post."""
	data = frappe.local.form_dict
	frappe.get_doc({
		"doctype": "WhatsApp Notification Log",
		"template": "Webhook",
		"meta_data": json.dumps(data)
	}).insert(ignore_permissions=True)

	messages = []
	try:
		messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
	except KeyError:
		messages = data["entry"]["changes"][0]["value"].get("messages", [])

	if messages:
		for message in messages:
			message_type = message['type']
			if message_type == 'text':
				frappe.get_doc({
					"doctype": "WhatsApp Message",
					"type": "Incoming",
					"from": message['from'],
					"message": message['text']['body'],
					"message_id": message['id'],
					"content_type":message_type
				}).insert(ignore_permissions=True)
			elif message_type in ["image", "audio", "video", "document"]:
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

						file_path = f"{bench_location}/sites/{site_name}/public/files/"

						file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
						file_full_path = file_path + file_name

						with open(file_full_path, "wb") as file:
							file.write(file_data)

						time.sleep(1)

						frappe.get_doc({
							"doctype": "WhatsApp Message",
							"type": "Incoming",
							"from": message['from'],
							"message_id": message['id'],
							"message": f"/files/{file_name}",
							"attach" : f"/files/{file_name}",
							"content_type" : message_type
						}).insert(ignore_permissions=True)
	else:
		changes = None
		try:
			changes = data["entry"][0]["changes"][0]
		except KeyError:
			changes = data["entry"]["changes"][0]
		update_status(changes)
	return


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
	doc.save(ignore_permissions=True)