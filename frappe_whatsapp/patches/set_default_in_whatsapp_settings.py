import frappe

def execute():
    settings = frappe.get_single("WhatsApp Settings")
    settings.allow_auto_read_receipt = 1
    settings.save()