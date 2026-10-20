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
		show_incoming_message(frm);
		if (frm.doc.type == 'Incoming'){
			frm.add_custom_button(__("Reply"), function(){
				frappe.new_doc("WhatsApp Message", {"to": frm.doc.from});

			});
		}

		// add custom button to send read receipt
		add_mark_as_read(frm);
	}
});

function show_incoming_message(frm) {
	if (frm.doc.type !== "Incoming") return;

	const preview = frm.get_field("incoming_message_preview");
	if (!preview) return;
	const $preview = preview.$wrapper;
	$preview.empty();

	if (frm.doc.message) {
		$("<div>")
			.addClass("well")
			.css("white-space", "pre-wrap")
			.text(frm.doc.message)
			.appendTo($preview);
	}

	if (!frm.doc.attach) return;

	const file_url = encodeURI(frm.doc.attach);
	if (frm.doc.content_type === "image") {
		$("<a>", { href: file_url, target: "_blank", rel: "noopener" })
			.append($("<img>", { src: file_url, alt: __("Incoming image") }).css({ "max-width": "100%", "max-height": "32rem" }))
			.appendTo($preview);
	} else if (frm.doc.content_type === "video") {
		$("<video>", { src: file_url, controls: true }).css("max-width", "100%").appendTo($preview);
	} else if (frm.doc.content_type === "audio") {
		$("<audio>", { src: file_url, controls: true }).css("width", "100%").appendTo($preview);
	} else {
		$("<a>", { href: file_url, target: "_blank", rel: "noopener", text: __("Open attachment") })
			.addClass("btn btn-default btn-sm")
			.appendTo($preview);
	}
}

// custom button
function add_mark_as_read(frm){
	if(frm.doc.type === "Outgoing" || frm.doc.status == "marked as read" || !frm.doc.message_id)
		return
	
	frappe.db.get_value('WhatsApp Account', frm.doc.whatsapp_account, 'allow_auto_read_receipt').then(value => {
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
