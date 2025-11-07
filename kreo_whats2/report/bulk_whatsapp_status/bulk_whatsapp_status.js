frappe.query_reports["Bulk WhatsApp Status"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nDraft\nQueued\nIn Progress\nCompleted\nPartially Failed"
        },
        // {
        //     "fieldname": "from_number",
        //     "label": __("From Number"),
        //     "fieldtype": "Link",
        //     "options": "WhatsApp Number"
        // }
    ]
};