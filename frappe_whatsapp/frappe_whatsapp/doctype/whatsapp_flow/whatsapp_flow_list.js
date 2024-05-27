frappe.listview_settings['WhatsApp Flow'] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Fetch flows from meta"), function() {
			frappe.call({
				method:'frappe_whatsapp.utils.flow.get_flows',
				callback: function(res) {
					frappe.msgprint(res.message)
					listview.refresh();
				}
			});
		});
	}
};