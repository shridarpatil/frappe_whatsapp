// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Message', {
	refresh: function(frm) {
		if (frm.doc.type == 'Incoming'){
			frm.add_custom_button(__("Reply"), function(){
				frappe.new_doc("WhatsApp Message", {"to": frm.doc.from});

			});
		}

		// add custom button to send read receipt
		add_mark_as_read(frm);
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

// custom button
function add_mark_as_read(frm){
	if(frm.doc.type === "Incoming" && frm.doc.status !== "marked as read" && frm.doc.message_id){
		frm.add_custom_button(__('Mark as read'), function(){
			send_read_receipt(frm);
		});
	}
}

function send_read_receipt(frm) {
	frappe.call({
		doc: frm.doc,
		method: "send_read_receipt",
		callback: function(r) {
			if (r && r.message) {
				frappe.msgprint(__('Marked as read'));
			}
		}
	});
}