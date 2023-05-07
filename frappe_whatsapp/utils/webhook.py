"""Webhook."""
import frappe
import json

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

#if messages:
        #for message in messages:
            #if message['type'] == 'text':
                
               
              #  frappe.get_doc({
              #      "doctype": "WhatsApp Message",
                #    "type": "Incoming",
                #    "from": message['from'],
                 #   "message": message['text']['body']
              #  }).insert(ignore_permissions=True)
                
        #    elif message['type'] == 'image':
          #      file_url = message['image']['url']
              #  file_name = message['image']['file_name']
            #    file_size = message['image']['file_size']
           #     file_data = frappe.utils.file_manager.get_file(file_url)
             #   save_url(file_name, file_data, "WhatsApp Attachments", "Home/Attachments", file_size=file_size)
              #  frappe.get_doc({
              #      "doctype": "WhatsApp Message",
                   # "type": "Incoming",
                  #  "from": message['from'],
                   # "attachment": {
                   #     "doctype": "File",
                   #     "file_name": file_name,
                   #     "file_url": file_url,
                     #   "file_size": file_size,
                    #    "is_private": 1
                  #  }
             #   }).insert(ignore_permissions=True)
       #     elif message['type'] == 'audio':
      #          file_url = message['audio']['url']
       #         file_name = message['audio']['file_name']
      #          file_size = message['audio']['file_size']
       #         file_data = frappe.utils.file_manager.get_file(file_url)
        #        save_url(file_name, file_data, "WhatsApp Attachments", "Home/Attachments", file_size=file_size)
         #       frappe.get_doc({
          #          "doctype": "WhatsApp Message",
          #          "type": "Incoming",
            #        "from": message['from'],
            #        "attachment": {
             #          "doctype": "File",
                 #       "file_name": file_name,
                 #       "file_url": file_url,
                 #       "file_size": file_size,
                  #      "is_private": 1
                  #  }
             #   }).insert(ignore_permissions=True)
         #   elif message['type'] == 'video':
           #     file_url = message['video']['url']
         #       file_name = message['video']['file_name']
           #     file_size = message['video']['file_size']
          #      file_data = frappe.utils.file_manager.get_file(file_url)
            #    save_url(file_name, file_data, "WhatsApp Attachments", "Home/Attachments", file_size=file_size)
           #     frappe.get_doc({
             #       "doctype": "WhatsApp Message",
                #    "type": "Incoming",
               #     "from": message['from'],
                #    "attachment": {
              #          "doctype": "File",
               #         "file_name": file_name,
               #         "file_url": file_url,
               #         "file_size": file_size,
               #         "is_private": 1
              #      }
             #   }).insert(ignore_permissions=True)


    if messages:
        for message in messages:
            if message['type'] == 'text':
                frappe.get_doc({
                    "doctype": "WhatsApp Message",
                    "type": "Incoming",
                    "from": message['from'],
                    "message": message['text']['body']
                }).insert(ignore_permissions=True)

                mobile_no = message['from']
                customer_name = frappe.db.get_value("Customer", filters={"mobile_no": mobile_no}, fieldname="name")
                frappe.logger.info("Messaggio inviato da " + customer_name + " (" + str(message['from']) + ")\n" + message['text']['body'])
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

