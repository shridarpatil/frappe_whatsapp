import frappe

def create_integrations_card():
    try:
        workspace = frappe.get_doc('Workspace', 'Integrations')
    except frappe.DoesNotExistError:
        frappe.throw("The Integrations workspace does not exist.")
    card_exists = any(d.label == "WhatsApp" for d in workspace.links)
    if not card_exists:
        card_break = {
            "type": "Card Break",
            "label": "WhatsApp",
        }
    links = [
        {
            "type": "Link",
            "label": "WhatsApp Templates",
            "link_type": "DocType",
            "link_to": "WhatsApp Templates"
        },
        {
            "type": "Link",
            "label": "WhatsApp Notification",
            "link_type": "DocType",
            "link_to": "WhatsApp Notification"
        },
        {
            "type": "Link",
            "label": "WhatsApp Message",
            "link_type": "DocType",
            "link_to": "WhatsApp Message"
        },
        {
            "type": "Link",
            "label": "WhatsApp Notification Log",
            "link_type": "DocType",
            "link_to": "WhatsApp Notification Log"
        },
        {
            "type": "Link",
            "label": "WhatsApp Settings",
            "link_type": "DocType",
            "link_to": "WhatsApp Settings"
        }
    ]
    workspace.append('links', card_break)
    for link in links:
        workspace.append('links', link)
    workspace.save()
    frappe.db.commit()
