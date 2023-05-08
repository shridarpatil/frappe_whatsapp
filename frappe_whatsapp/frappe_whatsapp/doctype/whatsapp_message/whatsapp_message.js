// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Message", {
    refresh: function(frm) {
        frappe.call({
            method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.set_to_field_options",
            args: {
                doc: frm.doc,
                method: "refresh"
            },
            callback: function(r) {
                frm.refresh_field("a");
            }
        });
    }
});
