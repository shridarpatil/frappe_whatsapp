import frappe
import requests
import json
import time
from frappe.integrations.utils import make_post_request, make_request
from frappe.utils import get_site_name

def gen_response(status, message, data=None):
	if data is None:
		data = []
	frappe.response['status_code'] = status
	frappe.response['message'] = message
	frappe.response['data'] = data

@frappe.whitelist(allow_guest=True)
def process_keywords_for_flow(self, method=None):
	try:
		message_text = self.message.strip().lower()
		number = getattr(self, "from")
		doc_type, doc = get_matching_document(message_text)
		if doc_type:
			response = process_document(doc_type, doc, number)
			return response
		else:
			return gen_response(404, "No Keyword found")
	except Exception as e:
		return handle_error("process_keywords_for_flow", frappe.get_traceback())

def get_matching_document(message_text):
	"""
	Searches for a document in the Frappe database that matches the provided message_text.

	Parameters:
	message_text (str): The text to search for in the database.

	Returns:
	tuple: A tuple containing the document type and the document itself, or (None, None) if no match is found.
	"""
	doc_types = ["WhatsApp Flow", "WhatsApp Interactive Message", "WhatsApp Option Message", "WhatsApp Keyword Message"]

	for doc_type in doc_types:
		if doc_type == "WhatsApp Flow":
			if frappe.db.exists(doc_type, {"words": message_text}):
				return doc_type, frappe.get_doc(doc_type, {"words": message_text})
		else:
			if frappe.db.exists(doc_type, {"name": message_text}):
				return doc_type, frappe.get_doc(doc_type, {"name": message_text})

	# Add a small delay to prevent overwhelming the database if necessary
	time.sleep(2)

	return None, None

@frappe.whitelist(allow_guest=True)
def process_document(doc_type, doc, number):
	if doc_type == "WhatsApp Flow":
		flow_id = doc.get('flow_id')
		message = doc.get('message')
		mode = doc.get('mode')
		flow_cta = doc.get('flow_cta')
		screen = doc.get('screen')
		header_text = doc.get('header_text')
		flow_action = doc.get('flow_action')
		if flow_action == "navigate":
			data = json.loads(doc.json)
			response = send_whatsapp_flow_message(flow_id, number, message, mode, flow_cta, screen, header_text, data)
		elif flow_action == "data_exchange":
			api_endpoint = doc.get('exchange_endpoint')
			api_call = make_request("GET", api_endpoint)
			data = api_call.get('data', [])
			response = send_whatsapp_flow_message(flow_id, number, message, mode, flow_cta, screen, header_text, data)

	elif doc_type == "WhatsApp Interactive Message":
		options = json.loads(doc.options)
		response = send_whatsapp_interactive_list_message(number, doc.header_text, doc.body_message, doc.footer_text, doc.action_button, doc.action_title, options)
	elif doc_type == "WhatsApp Option Message":
		options = json.loads(doc.options)
		response = send_whatsapp_message_with_buttons(number, doc.body_message, options)
	elif doc_type == "WhatsApp Keyword Message":
		response = send_whatsapp_message_for_keyword(number, doc.message)
	return response

def handle_error(title, message):
	frappe.log_error(title=title, message=message)
	return gen_response(500, "Something went wrong. Please try again.")

@frappe.whitelist(allow_guest=True)
def get_flow_token(flow_id):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{flow_id}?fields=preview.invalidate(false)"
	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}
	response = requests.get(url, headers=headers)
	response_data = response.json()
	preview_url = response_data['preview']['preview_url']
	flow_token = preview_url.split('=')[-1]
	return flow_token

def get_whatsapp_settings():
	return frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")

@frappe.whitelist(allow_guest=True)
def send_whatsapp_flow_message(flow_id, number, message, mode, flow_cta, screen, header_text, data):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{settings.version}/{settings.phone_id}/messages"
	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}
	flow_token = get_flow_token(flow_id)
	payload = json.dumps({
		"messaging_product": "whatsapp",
		"to": number,
		"recipient_type": "individual",
		"type": "interactive",
		"interactive": {
			"type": "flow",
			"header": {"type": "text", "text": header_text},
			"body": {"text": message},
			"action": {
				"name": "flow",
				"parameters": {
					"flow_message_version": "3",
					"flow_action": "navigate",
					"flow_token": flow_token,
					"flow_id": flow_id,
					"flow_cta": flow_cta,
					"mode": mode.lower(),
					"flow_action_payload": {
						"screen": screen,
						"data": data
					},
				},
			},
		},
	})
	response = requests.post(url, headers=headers, data=payload)
	response.raise_for_status()
	return response.json()

def send_whatsapp_interactive_list_message(number, header_text, body_text, footer_text, action_button, action_title, options):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{settings.version}/{settings.phone_id}/messages"
	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}
	sections = [{"title": action_title, "rows": options}]
	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"type": "interactive",
		"interactive": {
			"type": "list",
			"header": {"type": "text", "text": header_text},
			"body": {"text": body_text},
			"footer": {"text": footer_text},
			"action": {"button": action_button, "sections": sections}
		}
	}
	response = requests.post(url, headers=headers, json=payload)
	response.raise_for_status()
	return {"message": "Interactive message sent", "response": response.json()}

def send_whatsapp_message_with_buttons(number, body_text, options):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{settings.version}/{settings.phone_id}/messages"
	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}
	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"type": "interactive",
		"interactive": {
			"type": "button",
			"body": {"text": body_text},
			"action": {"buttons": options}
		}
	}
	response = requests.post(url, headers=headers, json=payload)
	response.raise_for_status()
	return response.json()


def send_whatsapp_message_for_keyword(number, message):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{settings.version}/{settings.phone_id}/messages"
	headers = {
		"authorization": f"Bearer {token}",
		"content-type": "application/json"
	}
	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"type": "text",
		"text": {
			"body": message
		}
	}
	response = requests.post(url, headers=headers, json=payload)
	response.raise_for_status()
	return response.json()

@frappe.whitelist()
def send_whatsapp_video_message_for_keyword(number):
	settings = get_whatsapp_settings()
	token = settings.get_password("token")
	url = f"{settings.url}/{settings.version}/{settings.phone_id}/messages"
	headers = {
		"authorization": f"Bearer {token}",
		"Content-Type": "application/json"
	}

	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"recipient_type": "individual",
		"type": "video",
		"video": {
			"link": "https://youtu.be/l0SL2tHENbI?si=QxaZSvtOUfEXu-0J",
			"caption": "Check out this video!"
		}
	}

	response = requests.post(url, headers=headers, json=payload)
	response.raise_for_status()

	return response.json()

@frappe.whitelist()
def get_flows():
	settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
	token = settings.get_password("token")
	url = settings.url
	version = settings.version
	business_id = settings.business_id

	headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}
	payload = {}
	try:
		response = make_request(
			"GET",
			f"{url}/{version}/{business_id}/flows?limit=1000",
			headers=headers,
		)

		for flow in response["data"]:
			flags = 1
			if frappe.db.exists("WhatsApp Flow", {"flow_name": flow["name"]}):
				doc = frappe.get_doc("WhatsApp Flow", {"flow_name": flow["name"]})
			else:
				flags = 0
				doc = frappe.new_doc("WhatsApp Flow")
				doc.flow_name = flow["name"]
				doc.flow_id = flow["id"]
			doc.mode = flow["status"]
			if flags:
				doc.db_update()
			else:
				doc.db_insert()
			frappe.db.commit()
	except Exception as e:
		res = frappe.flags.integration_request.json()["error"]
		error_message = res.get("error_user_msg", res.get("message"))
		frappe.throw(
			msg=error_message,
			title=res.get("error_user_title", "Error"),
		)

	return "Successfully fetched flows from meta"