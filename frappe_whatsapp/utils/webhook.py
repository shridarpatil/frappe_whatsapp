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
        "template": "Text Message",
        "meta_data": json.dumps(data)
    }).insert(ignore_permissions=True)

    messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
    for message in messages:
        if message['type'] == 'text':
            frappe.get_doc({
                "doctype": "WhatsApp Message",
                "type": "Incoming",
                "from": message['from'],
                "message": message['text']['body']
            }).insert(ignore_permissions=True)
    return
