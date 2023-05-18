"""Webhook."""
import frappe
import json
import requests
import time


from werkzeug.wrappers import Response

settings = frappe.get_doc(# ricavo il token di verifica
            "WhatsApp Settings", "WhatsApp Settings",
        )
token = settings.get_password("token")

@frappe.whitelist(allow_guest=True)
def webhook():
    """Meta webhook."""
    if frappe.request.method == "GET":
        return get()
    return post(token)




def get():
    """Get."""
    hub_challenge = frappe.form_dict.get("hub.challenge")
    webhook_verify_token = frappe.db.get_single_value(
        "Whatsapp Settings", "webhook_verify_token"
    )

    if frappe.form_dict.get("hub.verify_token") != webhook_verify_token:
        frappe.throw("Verify token does not match")

    return Response(hub_challenge, status=200)


def post(token):
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
                    "from": customer(message),
                    "message": message['text']['body'],
                    "view": ""  # il campo HTML è vuoto, nessun file multimediale in arrivo
                }).insert(ignore_permissions=True)
            elif message_type in ["image", "audio", "video", "document"]:
                media_id = message[message_type]["id"]
                headers = {
                    'Authorization': 'Bearer ' + token  # sostituisci con il tuo token di accesso
                }
                response = requests.get(f'https://graph.facebook.com/v16.0/{media_id}/', headers=headers)
                if response.status_code == 200:
                    media_data = response.json()
                    media_url = media_data.get("url")
                    mime_type = media_data.get("mime_type")
                    file_extension = mime_type.split('/')[1]

                    media_response = requests.get(media_url, headers=headers)
                    if media_response.status_code == 200:
                        file_data = media_response.content

                        file_path = "/opt/bench/frappe-bench/sites/ced.confcommercioimola.cloud/public/files/"  # sostituisci con il percorso desiderato
                        file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
                        file_full_path = file_path + file_name

                        with open(file_full_path, "wb") as file:
                            file.write(file_data)

                        time.sleep(1) #"dorme" per mezzo secondo 

                        #if message_type == "video":
                       #  view_html = f'<html><head><title>Player video</title></head><body><video controls><source src="/files/{file_name}" type="video/mp4">Il tuo browser non supporta il tag video.</video></body></html>'
                      #  elif message_type == "audio":
                        # view_html = f'<html><head><title>Player audio</title></head><body><audio controls><source src="/files/{file_name}" type="audio/mp3">Il tuo browser non supporta audio.</audio></body></html>'
                       # elif message_type == "image":
                       #  view_html = f'<html> <head> <style> .image-viewer {{ display: flex; align-items: center; justify-content: center; height: 100vh; }} .image-container {{ max-width: 100%; max-height: 100%; }} .image {{ max-width: 100%; max-height: 100%; }} </style> </head> <body> <div class="image-viewer"> <div class="image-container"> <img class="image" src="/files/{file_name}" alt="Image"> </div> </div> </body> </html>'
                      #  elif message_type == "document":
                      #   view_html = f'<html> <head> <title>Visualizzatore di documenti</title> <style> #document-viewer {{ width: 100%; height: 600px; }} </style> </head> <body> <div id="document-viewer"> <iframe src="/files/{file_name}" width="100%" height="100%"></iframe> </div> </body> </html>'

                        download_url = f"/files/{file_name}"

                        frappe.get_doc({
                            "doctype": "WhatsApp Message",
                            "type": "Incoming",
                            "from": customer(message),
                            "message": f"{message_type} file: {file_name}",
                            "view": f'<html><body><a href="{download_url}" download>Scarica il file</a></body></html>'
                        }).insert(ignore_permissions=True)
    else:
        changes = None
        try:
            changes = data["entry"][0]["changes"][0]
        except KeyError:
            changes = data["entry"]["changes"][0]
        update_status(changes)
    return


def customer(message):
    if (frappe.db.get_value("Customer", filters={"mobile_no": ("+" + str(message['from']))}, fieldname="customer_name")):
        return frappe.db.get_value("Customer", filters={"mobile_no": ("+" + str(message['from']))}, fieldname="customer_name")

    else:
        return "non registrato: " + "+" + str(message['from'])
    

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

