// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt


frappe.ui.form.on('WhatsApp Notification', {
	refresh: function (frm) {
		// When the form is refreshed, trigger the function to populate the recipient field
		populate_recipient_field(frm);
	},
	reference_doctype: function (frm) {
		// When the reference_doctype is changed, trigger the function to populate the recipient field
		populate_recipient_field(frm);
	}
});

function populate_recipient_field(frm) {
	var reference_doctype = frm.doc.reference_doctype;

	if (reference_doctype) {
		// Fetch the doctype metadata
		frappe.model.with_doctype(reference_doctype, function () {
			var meta = frappe.get_meta(reference_doctype);
			var phone_fields = [];

			// Iterate over the fields in the doctype and find fields with options 'Phone'
			meta.fields.forEach(function (field) {
				if ((field.fieldtype === 'Data' && field.options === 'Phone') || field.fieldtype === 'Phone') {
					phone_fields.push(field.fieldname);
				}
			});

			// Set the options for the field_name field
			frm.set_df_property('field_name', 'options', phone_fields.join('\n'));
			frm.refresh_field('field_name');
		});
	} else {
		// If no reference_doctype is selected, clear the field_name field options
		frm.set_df_property('field_name', 'options', '');
		frm.refresh_field('field_name');
	}
}

frappe.ui.form.on('WhatsApp Notification', {
	template: function (frm) {
		frm.events.fields(frm);
	},
	fields: function (frm) {
		// Ensure the 'fields' list is cleared before adding new items
		frm.doc.fields = [];

		if (!frm.doc.template) {
			return;
		}

		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'WhatsApp Templates',
				name: frm.doc.template
			},
			callback: function (r) {
				if (r.message) {
					let template_doc = r.message;
					let sample_values = template_doc.sample_values || '';
					let variables_to_add = sample_values.split(',')
						.map(variable => variable.trim())
						.filter(variable => variable);

					variables_to_add.forEach(variable => {
						let new_variable = frm.add_child('fields');
						new_variable.template_variable = variable;
						new_variable.ref_doctype = frm.doc.reference_doctype;

					});

					frm.refresh_field('fields');
				}
			}
		});
	}
});

frappe.ui.form.on('WhatsApp Notification', {
	refresh: function (frm) {
		frm.trigger("load_template")
	},
	template: function (frm) {
		frm.trigger("load_template")
	},
	load_template: function (frm) {
		frappe.db.get_value(
			"WhatsApp Templates",
			frm.doc.template,
			["template", "header_type"],
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
	}
});


frappe.ui.form.on('WhatsApp Notification', {
	// Trigger when the form is loaded
	onload: function (frm) {
		// Check if reference_doctype is already selected
		if (frm.doc.reference_doctype) {
			// Call the reference_doctype function to handle the already selected doctype
			frm.trigger('reference_doctype');
		}
	},

	// Trigger when the reference_doctype field is changed
	reference_doctype: function (frm) {
		if (frm.doc.reference_doctype) {
			// Call Frappe's REST API to fetch the doctype's metadata
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'DocType',
					name: frm.doc.reference_doctype
				},
				callback: function (response) {
					if (response.message) {
						let fields = response.message.fields;

						// Fetch custom fields for the doctype
						frappe.call({
							method: 'frappe.client.get_list',
							args: {
								doctype: 'Custom Field',
								filters: {
									dt: frm.doc.reference_doctype
								},
								fields: ['fieldname', 'fieldtype', 'label'],
								order_by: 'fieldname asc'
							},
							callback: function (custom_fields_response) {
								if (custom_fields_response.message) {
									// Combine standard and custom fields
									fields = fields.concat(custom_fields_response.message);

									// Sort fields by fieldname in ascending order
									fields.sort((a, b) => (a.fieldname > b.fieldname) ? 1 : ((b.fieldname > a.fieldname) ? -1 : 0));

									// Extract and transform the field names
									const fieldNames = fields
										.filter(field => !['Section Break', 'Column Break', 'Tab Break', 'Table', 'Table MultiSelect'].includes(field.fieldtype))
										.reduce((acc, field) => {
											acc[field.fieldname] = "";
											return acc;
										}, {});

									// Include the "name" field explicitly
									fieldNames["name"] = "";

									// Convert the object to JSON format
									let fieldNamesJson = JSON.stringify(fieldNames, null, 2);

									// Check the length of the JSON string
									const maxLength = 1000; // Adjust this value as needed based on your database schema
									if (fieldNamesJson.length > maxLength) {
										// Truncate the JSON string if it exceeds the maximum length
										fieldNamesJson = fieldNamesJson.substring(0, maxLength - 3) + '...';
									}

									// Update the options for the child table's document_field
									update_document_field_options(frm, fieldNames);
								}
							}
						});
					}
				}
			});
		} else {
			update_document_field_options(frm, {});
		}
	}
});

// Function to update the document_field options in the child table
function update_document_field_options(frm, fieldNames) {
	// Convert fieldNames object keys to an array of options
	const options = Object.keys(fieldNames).join('\n');

	// Iterate over the child table and update the document_field options
	frm.fields_dict['fields'].grid.update_docfield_property('field_name', 'options', options);

	// Refresh the field to apply the changes
	frm.refresh_field('fields');
}
