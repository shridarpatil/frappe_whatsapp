import frappe


def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "name",
            "label": "ID",
            "fieldtype": "Link",
            "options": "Bulk WhatsApp Message",
            "width": 120
        },
        {
            "fieldname": "title",
            "label": "Title",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "creation",
            "label": "Created On",
            "fieldtype": "Datetime",
            "width": 150
        },
        # {
        #     "fieldname": "from_number",
        #     "label": "From Number",
        #     "fieldtype": "Link",
        #     "options": "WhatsApp Number",
        #     "width": 150
        # },
        {
            "fieldname": "recipient_count",
            "label": "Total Recipients",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "sent_count",
            "label": "Messages Sent",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "delivered_count",
            "label": "Delivered",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "read_count",
            "label": "Read",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "failed_count",
            "label": "Failed",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Data",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date") and filters.get("to_date"):
        conditions += " AND creation BETWEEN %(from_date)s AND %(to_date)s"
    
    if filters.get("status"):
        conditions += " AND status = %(status)s"
        
    if filters.get("from_number"):
        conditions += " AND from_number = %(from_number)s"
    
    data = frappe.db.sql("""
        SELECT 
            name, 
            title, 
            creation, 
            recipient_count, 
            sent_count, 
            status 
        FROM 
            `tabBulk WhatsApp Message` 
        WHERE 
            docstatus = 1 
            {conditions}
        ORDER BY 
            creation DESC
    """.format(conditions=conditions), filters, as_dict=1)
    
    # Fetch additional stats for each bulk message
    for row in data:
        # Get delivered count
        row["delivered_count"] = frappe.db.count("WhatsApp Message", {
            "bulk_message_reference": row.name,
            "status": "delivered"
        })
        
        # Get read count
        row["read_count"] = frappe.db.count("WhatsApp Message", {
            "bulk_message_reference": row.name,
            "status": "read"
        })

         # Get read count
        row["sent_count"] = frappe.db.count("WhatsApp Message", {
            "bulk_message_reference": row.name,
            "status": "sent"
        })
        
        # Get failed count
        row["failed_count"] = frappe.db.count("WhatsApp Message", {
            "bulk_message_reference": row.name,
            "status": "failed"
        })
    
    return data
