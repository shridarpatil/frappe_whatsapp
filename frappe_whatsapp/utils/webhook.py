"""Webhook."""
import frappe
import json
import requests
import base64


from werkzeug.wrappers import Response


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
                    "message": message['text']['body']
                }).insert(ignore_permissions=True)
            elif message_type in ["image", "audio", "video", "document"]:
                frappe.log_error(json.dumps(message, indent=4))
                print(json.dumps(message, indent=4))

                # media_data = message[message_type]["data"]
                # file_extension = message[message_type]["extension"]
                # file_data = base64.b64decode(media_data)

                # file_path = "/opt/bench/media/"  # Sostituisci con il percorso desiderato
                # file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
                # file_full_path = file_path + file_name

                # with open(file_full_path, "wb") as file:
                   #  file.write(file_data)

             #    frappe.get_doc({
               #      "doctype": "WhatsApp Message",
              #       "type": "Incoming",
               #      "from": message['from'],
              #       "message": f"{message_type} file: {file_name}",
              #       "attachment": file_full_path
              #   }).insert(ignore_permissions=True)
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

import requests

def send_message_to_whatsapp_message(message):
    """Send message to WhatsApp Message."""
    url = "https://ced.confcommercioimola.cloud/api/method/frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.receive" 
    data = {
        "messaging_product": "whatsapp",
        "to": message['from'],
        "type": "incoming",
        "message": message['text']['body']
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        frappe.msgprint("Message sent to WhatsApp Message successfully!")
    except requests.exceptions.RequestException as e:
        frappe.log_error("Error sending message to WhatsApp Message: {}".format(str(e)))
