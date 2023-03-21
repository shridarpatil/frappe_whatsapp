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
			["template", "header_type"],
			(r) => {
				if (r && r.template) {
					if (r.header_type == 'DOCUMENT'){
						frm.toggle_display("attach_document_print", true);
						frm.set_value("attach_document_print", 1)
					}else{
						frm.toggle_display("attach_document_print", false);
						frm.set_value("attach_document_print", 0)
					}

					frm.set_value("code", r.template);
					frm.refresh_field("code")
				}
			}
		)
	}
});
