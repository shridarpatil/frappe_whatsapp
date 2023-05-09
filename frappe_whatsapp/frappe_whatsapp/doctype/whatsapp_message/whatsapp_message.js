// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Message", {
    refresh: function(frm) {
        frappe.db.get_list('Customer', { fields: ['name'] })
            .then(function(result) {
                var customerNames = result.map(function(item) {
                    return item.name;
                });
                cur_frm.set_df_property("a", "options", customerNames);
            });

        frm.fields_dict.mode.$input.on("change", function() {
            if (frm.doc.mode) {
                frm.set_df_property("a", "read_only", 1);
                frm.set_df_property("gruppo", "read_only", 0);
            } else {
                frm.set_df_property("a", "read_only", 0);
                frm.set_df_property("gruppo", "read_only", 1);
            }
        });
    }
});
