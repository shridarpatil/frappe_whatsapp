// Copyright (c) 2025, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Flow", {
    refresh(frm) {
        // Add action buttons based on flow status
        if (!frm.is_new()) {
            // Create on WhatsApp button
            if (!frm.doc.flow_id) {
                frm.add_custom_button(__("Create on WhatsApp"), function() {
                    frm.call({
                        method: "create_on_whatsapp",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Creating flow on WhatsApp..."),
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }, __("Actions"));
            }

            // Upload JSON button (if flow exists but not published)
            if (frm.doc.flow_id && frm.doc.status === "Draft") {
                frm.add_custom_button(__("Upload Flow JSON"), function() {
                    frm.call({
                        method: "upload_flow_json",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Uploading flow JSON..."),
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }, __("Actions"));

                frm.add_custom_button(__("Publish"), function() {
                    frappe.confirm(
                        __("Are you sure you want to publish this flow? Published flows cannot be edited."),
                        function() {
                            frm.call({
                                method: "publish_flow",
                                doc: frm.doc,
                                freeze: true,
                                freeze_message: __("Publishing flow..."),
                                callback: function(r) {
                                    frm.reload_doc();
                                }
                            });
                        }
                    );
                }, __("Actions"));
            }

            // Deprecate button (if published)
            if (frm.doc.flow_id && frm.doc.status === "Published") {
                frm.add_custom_button(__("Deprecate"), function() {
                    frappe.confirm(
                        __("Are you sure you want to deprecate this flow?"),
                        function() {
                            frm.call({
                                method: "deprecate_flow",
                                doc: frm.doc,
                                freeze: true,
                                freeze_message: __("Deprecating flow..."),
                                callback: function(r) {
                                    frm.reload_doc();
                                }
                            });
                        }
                    );
                }, __("Actions"));
            }

            // Preview, status, and test buttons (if flow exists)
            if (frm.doc.flow_id) {
                frm.add_custom_button(__("Send Test"), function() {
                    frappe.prompt([
                        {
                            fieldname: "phone_number",
                            label: __("Phone Number"),
                            fieldtype: "Data",
                            reqd: 1,
                            description: __("Enter phone number with country code (e.g., 919876543210). Must be a registered test number for draft flows.")
                        },
                        {
                            fieldname: "message",
                            label: __("Message"),
                            fieldtype: "Small Text",
                            default: "Please fill out the form below"
                        }
                    ],
                    function(values) {
                        frm.call({
                            method: "send_test",
                            doc: frm.doc,
                            args: {
                                phone_number: values.phone_number,
                                message: values.message
                            },
                            freeze: true,
                            freeze_message: __("Sending test flow..."),
                            callback: function(r) {
                                // Success message shown by server
                            }
                        });
                    },
                    __("Send Test Flow"),
                    __("Send")
                    );
                }, __("Actions"));

                frm.add_custom_button(__("Check Status"), function() {
                    frm.call({
                        method: "get_flow_status",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Checking flow status..."),
                        callback: function(r) {
                            frm.reload_doc();
                            if (r.message && r.message.validation_errors && r.message.validation_errors.length > 0) {
                                console.log("Validation errors:", r.message.validation_errors);
                            }
                        }
                    });
                }, __("Actions"));

                frm.add_custom_button(__("Get Preview URL"), function() {
                    frm.call({
                        method: "get_flow_preview",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Getting preview URL..."),
                        callback: function(r) {
                            frm.reload_doc();
                            if (r.message) {
                                frappe.msgprint({
                                    title: __("Preview URL"),
                                    message: `<a href="${r.message}" target="_blank">${r.message}</a>`,
                                    indicator: "green"
                                });
                            }
                        }
                    });
                }, __("Actions"));

                // Delete from WhatsApp button
                frm.add_custom_button(__("Delete from WhatsApp"), function() {
                    frappe.confirm(
                        __("Are you sure you want to delete this flow from WhatsApp? This cannot be undone."),
                        function() {
                            frm.call({
                                method: "delete_from_whatsapp",
                                doc: frm.doc,
                                freeze: true,
                                freeze_message: __("Deleting flow..."),
                                callback: function(r) {
                                    frm.reload_doc();
                                }
                            });
                        }
                    );
                }, __("Actions"));
            }
        }

        // Show status indicator
        if (frm.doc.status) {
            let indicator = "orange";
            if (frm.doc.status === "Published") indicator = "green";
            else if (frm.doc.status === "Deprecated") indicator = "gray";
            else if (frm.doc.status === "Blocked") indicator = "red";

            frm.page.set_indicator(frm.doc.status, indicator);
        }
    }
});
