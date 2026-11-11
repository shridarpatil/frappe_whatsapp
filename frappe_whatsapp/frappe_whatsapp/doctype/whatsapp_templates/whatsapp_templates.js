// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

// A template that has a Meta ID is linked both ways: saving it here submits
// the edit to Meta, and deleting it here deletes it on Meta. Make that
// visible before the user does either.

frappe.ui.form.on('WhatsApp Templates', {
	refresh: function(frm) {
		frm.meta_edit_confirmed = false;

		if (frm.is_new() || !frm.doc.id) {
			return;
		}

		frm.set_intro(
			__("This template is linked to Meta. Saving changes here submits them to Meta for review, and deleting it here can delete it on Meta too. Changes made in WhatsApp Manager appear here after Sync from Meta."),
			"blue"
		);

		// Replace the standard "Permanently delete?" prompt for this form.
		frm.savetrash = function() {
			confirm_template_delete(frm);
		};
	},

	validate: function(frm) {
		if (frm.is_new() || !frm.doc.id || frm.meta_edit_confirmed) {
			return;
		}

		frappe.validated = false;
		frappe.confirm(
			__("Saving will submit these changes to Meta, where the template {0} is reviewed again before it can be used. Continue?", [frm.doc.actual_name.bold()]),
			function() {
				frm.meta_edit_confirmed = true;
				frm.save();
			}
		);
	}
});

function confirm_template_delete(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Delete WhatsApp Template"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__("{0} is linked to Meta. Choose what to delete:", [frm.doc.actual_name.bold()])}</p>
					<ul>
						<li>${__("<b>Delete on Meta too</b> removes the template from your WhatsApp Business account. It can no longer be sent and this cannot be undone.")}</li>
						<li>${__("<b>Delete local copy only</b> removes it from this site and leaves it on Meta. Use Sync from Meta to bring it back.")}</li>
					</ul>`
			}
		],
		primary_action_label: __("Delete on Meta too"),
		primary_action: function() {
			delete_template(frm, dialog, 1);
		},
		secondary_action_label: __("Delete local copy only"),
		secondary_action: function() {
			delete_template(frm, dialog, 0);
		}
	});

	dialog.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
	dialog.show();
}

function delete_template(frm, dialog, delete_on_meta) {
	frappe.call({
		method: 'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.delete_template',
		args: {
			name: frm.doc.name,
			delete_on_meta: delete_on_meta
		},
		freeze: true,
		freeze_message: __("Deleting template..."),
		callback: function(r) {
			if (r.exc) {
				return;
			}
			dialog.hide();
			frappe.model.clear_doc(frm.doctype, frm.docname);
			frappe.set_route("List", "WhatsApp Templates");
		}
	});
}
