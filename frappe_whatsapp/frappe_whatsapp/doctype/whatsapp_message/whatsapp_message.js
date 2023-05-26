// Copyright (c) 2023, Shridhar Patil and contributors
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
      frappe.db.get_list('Customer Group', { fields: ['name'] })
        .then(function(result) {
          var groupNames = result.map(function(item) {
            return item.name;
          });
          cur_frm.set_df_property("gruppo", "options", groupNames);
        });
      frappe.db.get_list('WhatsApp Templates', { fields: ['name'] })
        .then(function(result) {
          var templateNames = result.map(function(item) {
            return item.name;
          });
          cur_frm.set_df_property("templates", "options", templateNames);
        });
      if (frm.doc.type == "Incoming") {
      frm.add_custom_button(__('reply to the message'), function(){
          var newDoc = frappe.model.get_new_doc("WhatsApp Message");
          newDoc.a = frm.doc.from;
          frappe.set_route("Form", "WhatsApp Message", newDoc.name);
      }, __("reply"));
        if (((frm.doc.from).split(":")[0]) == "not registered") {
         frm.add_custom_button(__('register customer'), function(){
          var newDoc = frappe.model.get_new_doc("Customer");
          newDoc.mobile_no = ((frm.doc.from).split(":")[1]);
          frappe.set_route("Form", "Customer", newDoc.name);
         }, __("register"));
        }
        if (((frm.doc.message).split(":")[0]) == "media") {
          frm.add_custom_button(__('download media'), function(){
          var fileUrl = "https://ced.confcommercioimola.cloud/files/" + ((frm.doc.message).split(":")[1]);
          window.open(fileUrl);
         }, __("download"));
        }
      }

    },
    switch: function(frm) {
      if (frm.doc.switch) {
        cur_frm.set_df_property("a", "read_only", 1);
        cur_frm.set_df_property("gruppo", "read_only", 0);
        cur_frm.set_df_property("templates", "read_only", 1);
        cur_frm.set_df_property("notifica", "read_only", 1);
      } else {
        cur_frm.set_df_property("a", "read_only", 0);
        cur_frm.set_df_property("gruppo", "read_only", 1);
        cur_frm.set_df_property("templates", "read_only", 0);
        cur_frm.set_df_property("notifica", "read_only", 0);
      }
    },
    notifica: function(frm) {
      if (frm.doc.notifica) {
        cur_frm.set_df_property("a", "read_only", 1);
        cur_frm.set_df_property("gruppo", "read_only", 1);
        cur_frm.set_df_property("switch", "read_only", 1);
        cur_frm.set_df_property("templates", "read_only", 0);
      } else {
        cur_frm.set_df_property("a", "read_only", 0);
        cur_frm.set_df_property("gruppo", "read_only", 0);
        cur_frm.set_df_property("switch", "read_only", 0);
        cur_frm.set_df_property("templates", "read_only", 1);
      }
    }
  });
  