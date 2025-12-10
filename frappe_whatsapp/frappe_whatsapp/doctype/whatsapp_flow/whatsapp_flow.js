// Copyright (c) 2025, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Flow", {
    refresh(frm) {
        // Import from Meta button (for new docs or docs without flow_id)
        if (frm.is_new() || !frm.doc.flow_id) {
            frm.add_custom_button(__("Import from Meta"), function() {
                show_import_dialog(frm);
            }, __("Actions"));
        }

        // Add action buttons based on flow status
        if (!frm.is_new()) {
            // Sync from Meta button (if flow_id exists)
            if (frm.doc.flow_id) {
                frm.add_custom_button(__("Sync from Meta"), function() {
                    frm.call({
                        method: "sync_from_whatsapp",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Syncing flow from Meta..."),
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }, __("Actions"));
            }

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


function show_import_dialog(frm) {
    // First, select WhatsApp Account
    let account_dialog = new frappe.ui.Dialog({
        title: __("Import Flow from Meta"),
        fields: [
            {
                fieldname: "whatsapp_account",
                fieldtype: "Link",
                label: __("WhatsApp Account"),
                options: "WhatsApp Account",
                reqd: 1,
                default: frm.doc.whatsapp_account
            }
        ],
        primary_action_label: __("Fetch Flows"),
        primary_action: function(values) {
            account_dialog.hide();
            fetch_and_show_flows(values.whatsapp_account, frm);
        }
    });
    account_dialog.show();
}


function fetch_and_show_flows(whatsapp_account, frm) {
    frappe.call({
        method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_flow.whatsapp_flow.get_whatsapp_flows",
        args: {
            whatsapp_account: whatsapp_account
        },
        freeze: true,
        freeze_message: __("Fetching flows from Meta..."),
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                show_flows_selection_dialog(r.message, whatsapp_account, frm);
            } else {
                frappe.msgprint(__("No flows found on Meta Business Account"));
            }
        }
    });
}


function show_flows_selection_dialog(flows, whatsapp_account, frm) {
    // Build HTML table of flows
    let flow_rows = flows.map(flow => {
        let status_badge = flow.status === "PUBLISHED"
            ? '<span class="badge badge-success">Published</span>'
            : '<span class="badge badge-warning">Draft</span>';

        let exists_badge = flow.exists_locally
            ? `<span class="badge badge-info">Exists: ${flow.local_name}</span>`
            : '<span class="badge badge-secondary">Not imported</span>';

        let import_btn = flow.exists_locally
            ? `<button class="btn btn-xs btn-default" disabled>Already Imported</button>`
            : `<button class="btn btn-xs btn-primary import-flow-btn" data-flow-id="${flow.id}" data-flow-name="${flow.name}">Import</button>`;

        return `
            <tr>
                <td>${flow.name}</td>
                <td><code>${flow.id}</code></td>
                <td>${status_badge}</td>
                <td>${exists_badge}</td>
                <td>${import_btn}</td>
            </tr>
        `;
    }).join("");

    let dialog = new frappe.ui.Dialog({
        title: __("Select Flow to Import"),
        size: "large",
        fields: [
            {
                fieldname: "flows_html",
                fieldtype: "HTML",
                options: `
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>${__("Flow Name")}</th>
                                <th>${__("Flow ID")}</th>
                                <th>${__("Status")}</th>
                                <th>${__("Local Status")}</th>
                                <th>${__("Action")}</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${flow_rows}
                        </tbody>
                    </table>
                `
            }
        ]
    });

    dialog.show();

    // Attach click handlers to import buttons
    dialog.$wrapper.find(".import-flow-btn").on("click", function() {
        let flow_id = $(this).data("flow-id");
        let flow_name = $(this).data("flow-name");

        dialog.hide();
        import_flow(whatsapp_account, flow_id, flow_name, frm);
    });
}


function import_flow(whatsapp_account, flow_id, flow_name, frm) {
    frappe.call({
        method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_flow.whatsapp_flow.import_flow_from_whatsapp",
        args: {
            whatsapp_account: whatsapp_account,
            flow_id: flow_id,
            flow_name: flow_name
        },
        freeze: true,
        freeze_message: __("Importing flow..."),
        callback: function(r) {
            if (r.message) {
                frappe.set_route("Form", "WhatsApp Flow", r.message);
            }
        }
    });
}
