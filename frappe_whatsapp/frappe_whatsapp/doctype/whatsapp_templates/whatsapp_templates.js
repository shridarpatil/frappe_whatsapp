// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Templates', {
	refresh: function(frm) {
		// Meta's edit limit note, built on the server in the user's time zone.
		const edit_status = frm.doc.__onload && frm.doc.__onload.meta_edit_status;
		if (frm.is_new() || !edit_status) return;

		frm.set_intro(edit_status.message, edit_status.color);
	}
});
