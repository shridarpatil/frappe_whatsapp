frappe.listview_settings['WhatsApp Templates'] = {

	onload: function(listview) {
		listview.page.add_inner_button(__("Sync from Meta"), function() {
			frappe.call({
				method: 'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.fetch',
				freeze: true,
				freeze_message: __("Syncing templates from Meta..."),
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({
							title: __("Sync Complete"),
							message: r.message,
							indicator: "green"
						});
						listview.refresh();
					}
				}
			});
		});
	}
};