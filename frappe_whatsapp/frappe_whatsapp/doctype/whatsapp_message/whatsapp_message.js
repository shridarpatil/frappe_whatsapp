// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Message', {
	refresh: function(frm) {
		if (frm.doc.type == 'Incoming'){
			frm.add_custom_button(__("Reply"), function(){
				frappe.new_doc("WhatsApp Message", {"to": frm.doc.from});

			});
		}
	},

	use_template: function(frm){
		// set to default
		frm.set_value("message_type", "Manual");

		if (frm.doc.use_template) {
			frm.set_value("message_type", "Template");
		}

		frm.refresh_field("message_type");
	}
});
