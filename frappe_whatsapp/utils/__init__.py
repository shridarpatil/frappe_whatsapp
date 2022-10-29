"""Run on each event."""
import frappe

from frappe.core.doctype.server_script.server_script_utils import EVENT_MAP


def ping():
    return "pong"


def run_server_script_for_doc_event(doc, event):
    """Run on each event."""
    if event not in EVENT_MAP:
        return

    if frappe.flags.in_install:
        return

    if frappe.flags.in_migrate:
        return
    notification = get_notifications_map().get(
        doc.doctype, {}
    ).get(EVENT_MAP[event], None)

    if notification:
        # run all scripts for this doctype + event
        for notification_name in notification:
            print(notification_name)
            frappe.get_doc("WhatsApp Notification", notification_name).execute_doc(doc)


def get_notifications_map():
    """Get mapping."""
    if frappe.flags.in_patch and not frappe.db.table_exists("WhatsApp Notification"):
        return {}

    notification_map = frappe.cache().get_value("whatsapp_notification_map")
    if notification_map is None:
        notification_map = {}
        enabled_whatsapp_notifications = frappe.get_all(
            "WhatsApp Notification",
            fields=("name", "reference_doctype", "doctype_event", "notification_type"),
            filters={"disabled": 0},
        )
        for notification in enabled_whatsapp_notifications:
            if notification.notification_type == "DocType Event":
                notification_map.setdefault(notification.reference_doctype, {}).setdefault(
                    notification.doctype_event, []
                ).append(notification.name)

        frappe.cache().set_value("whatsapp_notification_map", notification_map)

    return notification_map
