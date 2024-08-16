// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt
frappe.notification = {
	setup_fieldname_select: function (frm) {
		// get the doctype to update fields
		if (!frm.doc.reference_doctype) {
			return;
		}

		frappe.model.with_doctype(frm.doc.reference_doctype, function () {
			let get_select_options = function (df, parent_field) {
				// Append parent_field name along with fieldname for child table fields
				let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;
				let path = parent_field ? parent_field + " > " + df.fieldname : df.fieldname;

				return {
					value: select_value,
					label: path + " (" + __(df.label, null, df.parent) + ")",
				};
			};

			let get_date_change_options = function () {
				let date_options = $.map(fields, function (d) {
					return d.fieldtype == "Date" || d.fieldtype == "Datetime"
						? get_select_options(d)
						: null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: "creation", label: `creation (${__("Created On")})` },
					{ value: "modified", label: `modified (${__("Last Modified Date")})` },
				]);
			};

			let fields = frappe.get_doc("DocType", frm.doc.reference_doctype).fields;
			let options = $.map(fields, function (d) {
				return frappe.model.no_value_type.includes(d.fieldtype)
					? null
					: get_select_options(d);
			});

			// set date changed options
			frm.set_df_property("date_changed", "options", get_date_change_options());

		});
	}
};


frappe.ui.form.on('WhatsApp Notification', {
	refresh: function(frm) {
		frm.trigger("load_template")
		frappe.notification.setup_fieldname_select(frm);
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
					frm.set_value('header_type', r.header_type)
					frm.refresh_field("header_type")
					if (['DOCUMENT', "IMAGE"].includes(r.header_type)){
						frm.toggle_display("custom_attachment", true);
						frm.toggle_display("attach_document_print", true);
						if (!frm.doc.custom_attachment){
							frm.set_value("attach_document_print", 1)
						}
					}else{
						frm.toggle_display("custom_attachment", false);
						frm.toggle_display("attach_document_print", false);
						frm.set_value("attach_document_print", 0)
						frm.set_value("custom_attachment", 0)
					}

					frm.refresh_field("custom_attachment")

					frm.set_value("code", r.template);
					frm.refresh_field("code")
				}
			}
		)
	},
	custom_attachment: function(frm){
		if(frm.doc.custom_attachment == 1 &&  ['DOCUMENT', "IMAGE"].includes(frm.doc.header_type)){
			frm.set_df_property('file_name', 'reqd', frm.doc.custom_attachment)
		}else{
			frm.set_df_property('file_name', 'reqd', 0)
		}

		// frm.toggle_display("attach_document_print", !frm.doc.custom_attachment);
		if(frm.doc.header_type){
			frm.set_value("attach_document_print", !frm.doc.custom_attachment)
		}
	},
	attach_document_print: function(frm){
		// frm.toggle_display("custom_attachment", !frm.doc.attach_document_print);
		if(['DOCUMENT', "IMAGE"].includes(frm.doc.header_type)){
			frm.set_value("custom_attachment", !frm.doc.attach_document_print)
		}
	},
	reference_doctype: function (frm) {
		frappe.notification.setup_fieldname_select(frm);
	},
});


frappe.ui.form.on('WhatsApp Notification', {
    refresh: function (frm) {
        frm.add_custom_button(__('Get Alerts for Today'), function () {
            frappe.call({
                method: 'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_notification.custom_api.call_trigger_notifications',
                args: {
                    method: 'daily'  // You can change this as needed
                },
                callback: function (response) {
                    // Handle the response as needed
                    if (response.message) {
                        console.log(response.message);
                    }
                },
                error: function (error) {
                    console.error('Error:', error);
                    frappe.msgprint(__('Failed to trigger notifications'));
                }
            });
        });
    }
});