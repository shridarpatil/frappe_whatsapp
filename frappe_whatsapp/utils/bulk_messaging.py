import json
import frappe
from frappe.utils import cint


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
    print(data_fields)
    if data_fields and isinstance(data_fields, str):
        data_fields = json.loads(data_fields)
        
    doc = frappe.get_doc("WhatsApp Recipient List", list_name)
    count = doc.import_list_from_doctype(doctype, mobile_field, name_field, filters, limit, data_fields)
    doc.save()
    
    return count

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
