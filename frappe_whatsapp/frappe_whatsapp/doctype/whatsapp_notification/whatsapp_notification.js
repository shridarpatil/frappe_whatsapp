// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Notification', {
	refresh: function(frm) {
		frm.trigger("load_template")
	},
	template: function(frm){
		frm.trigger("load_template")
	},
	load_template: function(frm){
		frappe.db.get_value(
			"WhatsApp Templates",
			frm.doc.template,
			"template",
			(r) => {
				if (r && r.template) {
					frm.set_value("code", r.template);
					frm.refresh_field("code")
				}
			}
		)
	}
});
