// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsAppMessage", {
    onload: function(frm) {
        frappe.call({
            method: "frappe_whatsapp.whatsapp_message.py.set_to_field_options",
            callback: function(r) {
                frm.refresh_field("to");
            }
        });
    }
});