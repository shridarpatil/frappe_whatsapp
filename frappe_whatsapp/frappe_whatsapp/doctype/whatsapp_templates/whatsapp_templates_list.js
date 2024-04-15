frappe.listview_settings['WhatsApp Templates'] = {
	add_fields : ["status"],
	get_indicator: function(doc) {
       
		var status_color = {
			"approved" : "green",
			"pending" : "orange",
			"rejected" : "red"
        };

		return [__(doc.status || ""), status_color[(doc.status || "").toLowerCase()], `status,=,${doc.status}|docstatus,=,0`];
		
	},

	onload: function(listview) {
		listview.page.add_menu_item(__("Fetch templates from meta"), function() {
			frappe.call({
				method:'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.fetch',
				callback: function(res) {
					frappe.msgprint(res.message)
					listview.refresh();
				}
			});
		});
	}
};
