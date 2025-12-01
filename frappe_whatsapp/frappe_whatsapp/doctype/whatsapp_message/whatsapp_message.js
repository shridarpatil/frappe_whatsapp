// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Message', {
	onload: function(frm) {
		frappe.db.get_value('WhatsApp Account', frm.doc.whatsapp_account, 'allow_auto_read_receipt').then(value => {
			if (value && frm.doc.type === "Incoming" && frm.doc.status !== "marked as read" && frm.doc.message_id) {
				send_read_receipt(frm);
			}
		});
	},
	refresh: function(frm) {
		if (frm.doc.type == 'Incoming'){
			frm.add_custom_button(__("Reply"), function(){
				frappe.new_doc("WhatsApp Message", {"to": frm.doc.from});

			});
		}

		// add custom button to send read receipt
		add_mark_as_read(frm);
	}
});

// custom button
function add_mark_as_read(frm){
	if(frm.doc.type === "Outgoing" || frm.doc.status == "marked as read" || !frm.doc.message_id)
		return
	
	frappe.db.get_single_value('WhatsApp Settings', 'allow_auto_read_receipt').then(value => {
		if (value) return; // return if auto read receipt is enabled

		frm.add_custom_button(__('Mark as read'), function(){
			send_read_receipt(frm);
		});
	});
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
