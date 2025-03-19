import re
import frappe

class WhatsAppSettings(frappe.model.document.Document):
    def before_save(self):
        validate_cron_format(self.cron_time)

    def on_update(self):
        update_cron_job(self)


def validate_cron_format(cron_time):
    """Validate the cron format."""
    cron_pattern = r"^(\d{1,2}|\*) (\d{1,2}|\*) (\d{1,2}|\*) (\d{1,2}|\*) (\d{1,2}|\*)$"
    if not re.match(cron_pattern, cron_time):
        frappe.throw("Invalid cron format. Use '* * * * *' style (minute hour day month weekday)")


def update_cron_job(doc):
    """Create or update Scheduled Job Type and Scheduler Event when cron_time changes."""
    scheduled_against_value = "WhatsApp Notification"
    method_value = "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_notification.whatsapp_notification.trigger_notifications"

    # Check if Scheduler Event exists
    sch_event_name = frappe.db.get_value("Scheduler Event", {"scheduled_against": scheduled_against_value}, "name")
    if sch_event_name:
        # Update existing Scheduler Event
        sch_event = frappe.get_doc("Scheduler Event", sch_event_name)
        sch_event.method = method_value  # Set the method field
        sch_event.save(ignore_permissions=True)  # Save to ensure any updates are persisted
    else:
        # Create new Scheduler Event
        sch_event = frappe.new_doc("Scheduler Event")
        sch_event.scheduled_against = scheduled_against_value
        sch_event.method = method_value  # Set the method field
        sch_event.save(ignore_permissions=True)
        sch_event_name = sch_event.name

    # Check if Scheduled Job Type exists
    job_name = frappe.db.get_value(
        "Scheduled Job Type",
        {
            "method": method_value
        },
        "name"
    )

    if job_name:
        # Update existing job
        job = frappe.get_doc("Scheduled Job Type", job_name)
        job.cron_format = doc.cron_time
        job.scheduler_event = sch_event_name  # Ensure the scheduler event is linked
        job.save(ignore_permissions=True)
        frappe.msgprint("Whatsapp Notification Time Updated Successfully!")
    else:
        # Create new Scheduled Job Type
        job = frappe.new_doc("Scheduled Job Type")
        job.method = method_value
        job.frequency = "Cron"
        job.scheduler_event = sch_event_name
        job.cron_format = doc.cron_time
        job.save(ignore_permissions=True)
        frappe.msgprint("New cron job created!")