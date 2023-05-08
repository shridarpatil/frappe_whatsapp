// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Message", {
    refresh: function(frm) {
      cur_frm.set_df_property("a", "options", ['option a', 'option b']);
    }
});
