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

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));
		});
	},
	setup_alerts_button: function (frm) {
		// body...
		frm.add_custom_button(__('Get Alerts for Today'), function () {
			frappe.call({
				method: 'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_notification.whatsapp_notification.call_trigger_notifications',
				args: {
					method: 'daily'
				},
				callback: function (response) {
					if (response.message && response.message.length > 0) {
					} else {
						frappe.msgprint(__('No alerts for today'));
					}
				},
				error: function (error) {
					frappe.msgprint(__('Failed to trigger notifications'));
				}
			});
		});
	}
};


frappe.ui.form.on('WhatsApp Notification', {
	refresh: function (frm) {
		frm.trigger("load_template")
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_alerts_button(frm);
	},
	template: function (frm) {
		frm.trigger("load_template");
	},

	load_template: function (frm) {
		frappe.db.get_value(
			"WhatsApp Templates",
			frm.doc.template,
			["template", "header_type", "need_button_in_template", "template_buttons_json", "need_dynamic_button_url_parameter", "field_name_for_button_parameter"],
			(r) => {
				if (r && r.template) {
					frm.set_value('header_type', r.header_type)
					frm.refresh_field("header_type")
					if (['DOCUMENT', "IMAGE"].includes(r.header_type)) {
						frm.toggle_display("custom_attachment", true);
						frm.toggle_display("attach_document_print", true);
						if (!frm.doc.custom_attachment) {
							frm.set_value("attach_document_print", 1)
						}
					} else {
						frm.toggle_display("custom_attachment", false);
						frm.toggle_display("attach_document_print", false);
						frm.set_value("attach_document_print", 0)
						frm.set_value("custom_attachment", 0)
					}

					frm.refresh_field("custom_attachment")

					frm.set_value("code", r.template);
					frm.refresh_field("code")
				}

				if (r && r.need_button_in_template) {
					let button_urls = "";
					r.template_buttons_json = JSON.parse(r.template_buttons_json)

					// Build button URLs string from template buttons
					r.template_buttons_json.forEach(btn => {
						button_urls += btn.url + "\n";
						button_urls = button_urls.trim();
					});

					// Only update if value changed to keep form clean
					if (frm.doc.button_urls !== button_urls) {
						frm.set_value('button_urls', button_urls);
					}

					if (r.need_dynamic_button_url_parameter) {
						// Extract potential dynamic fields from template
						const fields = r.field_name_for_button_parameter ? r.field_name_for_button_parameter.split("\n") : [];
						let existing_fields = (frm.doc.button_url_fields || []).map(row => row.field_name);

						// Replace only if the field set is different (avoid dirty form)
						if (JSON.stringify(existing_fields) !== JSON.stringify(fields)) {
							frm.clear_table("button_url_fields");

							// Populate child table with dynamic fields
							fields.forEach(field => {
								frm.add_child("button_url_fields", { field_name: field });
							});
						}
					}

					frm.refresh_field("button_urls");
					frm.refresh_field("button_url_fields");
				}
			}
		)
	},
	custom_attachment: function (frm) {
		if (frm.doc.custom_attachment == 1 && ['DOCUMENT', "IMAGE"].includes(frm.doc.header_type)) {
			frm.set_df_property('file_name', 'reqd', frm.doc.custom_attachment)
		} else {
			frm.set_df_property('file_name', 'reqd', 0)
		}

		// frm.toggle_display("attach_document_print", !frm.doc.custom_attachment);
		if (frm.doc.header_type) {
			frm.set_value("attach_document_print", !frm.doc.custom_attachment)
		}
	},
	attach_document_print: function (frm) {
		// frm.toggle_display("custom_attachment", !frm.doc.attach_document_print);
		if (['DOCUMENT', "IMAGE"].includes(frm.doc.header_type)) {
			frm.set_value("custom_attachment", !frm.doc.attach_document_print)
		}
	},
	reference_doctype: function (frm) {
		frappe.notification.setup_fieldname_select(frm);
	},
});
