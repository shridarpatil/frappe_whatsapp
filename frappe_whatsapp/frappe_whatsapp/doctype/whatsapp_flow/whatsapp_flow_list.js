// Copyright (c) 2025, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.listview_settings["WhatsApp Flow"] = {
    onload: function(listview) {
        listview.page.add_inner_button(__("Sync from Meta"), function() {
            frappe.prompt([
                {
                    fieldname: "whatsapp_account",
                    fieldtype: "Link",
                    label: __("WhatsApp Account"),
                    options: "WhatsApp Account",
                    reqd: 1
                }
            ],
            function(values) {
                frappe.call({
                    method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_flow.whatsapp_flow.sync_all_flows",
                    args: {
                        whatsapp_account: values.whatsapp_account
                    },
                    freeze: true,
                    freeze_message: __("Syncing all flows from Meta..."),
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __("Sync Complete"),
                                message: __("Imported: {0}<br>Updated: {1}<br>Skipped: {2}",
                                    [r.message.imported, r.message.updated, r.message.skipped]),
                                indicator: "green"
                            });
                            listview.refresh();
                        }
                    }
                });
            },
            __("Sync Flows from Meta"),
            __("Sync All")
            );
        });
    }
};
