import json
import frappe
from frappe.utils import cint, now


@frappe.whitelist()
def get_progress(name):
    """Get progress for a bulk message"""
    doc = frappe.get_doc("Bulk WhatsApp Message", name)
    return doc.get_progress()

@frappe.whitelist()
def retry_failed(name):
    """Retry failed messages"""
    doc = frappe.get_doc("Bulk WhatsApp Message", name)
    doc.retry_failed()
    return True

@frappe.whitelist()
def import_recipients(list_name, doctype, mobile_field, name_field=None, filters=None, limit=None, data_fields=None):
    """Import recipients from a DocType"""
    if filters and isinstance(filters, str):
        filters = json.loads(filters)

    if data_fields and isinstance(data_fields, str):
        data_fields = json.loads(data_fields)
        
    doc = frappe.get_doc("WhatsApp Recipient List", list_name)
    count = doc.import_list_from_doctype(doctype, mobile_field, name_field, filters, limit, data_fields)
    doc.save()
    
    return count

def process_scheduled_bulk_messages():
    """Check for scheduled bulk messages whose time has arrived and queue them."""
    scheduled = frappe.get_all(
        "Bulk WhatsApp Message",
        filters={
            "status": "Scheduled",
            "docstatus": 1,
            "scheduled_time": ["<=", now()],
        },
        pluck="name",
    )

    for name in scheduled:
        # Claim the campaign before enqueuing anything. queue_messages() calls
        # frappe.enqueue_doc, which pushes to redis immediately
        # (enqueue_after_commit defaults to False), so the "Queued" flip has to
        # be durable first: if it were still uncommitted when a later campaign
        # raised, the rollback would revert this one to "Scheduled" while its
        # recipient jobs were already queued, and the next tick would enqueue
        # every recipient a second time.
        frappe.db.set_value("Bulk WhatsApp Message", name, "status", "Queued")
        # nosemgrep: frappe-manual-commit -- scheduler job outside request scope; the status must be durable before enqueue_doc hands the jobs to redis
        frappe.db.commit()

        try:
            frappe.get_doc("Bulk WhatsApp Message", name).queue_messages()
        except Exception:
            # Roll back so a DB-level failure doesn't poison the transaction for
            # the remaining campaigns (and so log_error can write).
            frappe.db.rollback()
            frappe.log_error(
                title=f"Bulk WhatsApp Message scheduling failed: {name}"
            )


@frappe.whitelist()
def schedule_bulk_messages():
    """Background job to process bulk WhatsApp messages"""
    # Find queued bulk messages with recipient counts less than sent counts
    bulk_messages = frappe.get_all(
        "Bulk WhatsApp Message", 
        filters={
            "status": "Queued",
            "docstatus": 1
        },
        fields=["name", "recipient_count", "sent_count"]
    )
    
    for bulk in bulk_messages:
        # Skip if all messages have been sent
        if cint(bulk.sent_count) >= cint(bulk.recipient_count):
            frappe.db.set_value("Bulk WhatsApp Message", bulk.name, "status", "Completed")
            continue
            
        # Check for failed messages
        failed_count = frappe.db.count("WhatsApp Message", {
            "bulk_message_reference": bulk.name,
            "status": "Failed"
        })
        
        # If all messages are either sent or failed
        if cint(bulk.sent_count) - failed_count + cint(failed_count) >= cint(bulk.recipient_count):
            if failed_count > 0:
                frappe.db.set_value("Bulk WhatsApp Message", bulk.name, "status", "Partially Failed")
            else:
                frappe.db.set_value("Bulk WhatsApp Message", bulk.name, "status", "Completed")
