"""Run on each event."""
import frappe

from frappe.core.doctype.server_script.server_script_utils import EVENT_MAP


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
            frappe.get_doc(
                "WhatsApp Notification",
                notification_name
            ).send_template_message(doc)


def get_notifications_map():
    """Get mapping."""
    if frappe.flags.in_patch and not frappe.db.table_exists("WhatsApp Notification"):
        return {}

    notification_map = {}
    enabled_whatsapp_notifications = frappe.get_all(
        "WhatsApp Notification",
        fields=("name", "reference_doctype", "doctype_event", "notification_type"),
        filters={"disabled": 0},
    )
    for notification in enabled_whatsapp_notifications:
        if notification.notification_type == "DocType Event":
            notification_map.setdefault(
                notification.reference_doctype, {}
            ).setdefault(
                notification.doctype_event, []
            ).append(notification.name)

    frappe.cache().set_value("whatsapp_notification_map", notification_map)

    return notification_map


def trigger_whatsapp_notifications_all():
    """Run all."""
    trigger_whatsapp_notifications("All")


def trigger_whatsapp_notifications_hourly():
    """Run hourly."""
    trigger_whatsapp_notifications("Hourly")


def trigger_whatsapp_notifications_daily():
    """Run daily."""
    trigger_whatsapp_notifications("Daily")


def trigger_whatsapp_notifications_weekly():
    """Trigger notification."""
    trigger_whatsapp_notifications("Weekly")


def trigger_whatsapp_notifications_monthly():
    """Trigger notification."""
    trigger_whatsapp_notifications("Monthly")


def trigger_whatsapp_notifications_yearly():
    """Trigger notification."""
    trigger_whatsapp_notifications("Yearly")


def trigger_whatsapp_notifications_hourly_long():
    """Trigger notification."""
    trigger_whatsapp_notifications("Hourly Long")


def trigger_whatsapp_notifications_daily_long():
    """Trigger notification."""
    trigger_whatsapp_notifications("Daily Long")


def trigger_whatsapp_notifications_weekly_long():
    """Trigger notification."""
    trigger_whatsapp_notifications("Weekly Long")


def trigger_whatsapp_notifications_monthly_long():
    """Trigger notification."""
    trigger_whatsapp_notifications("Monthly Long")


def trigger_whatsapp_notifications(event):
    """Run cron."""
    frappe.get_doc(
        "WhatsApp Notification",
        frappe.db.get_value("WhatsApp Notification", filters={"event_frequency": event})
    ).send_scheduled_message()
    pass
