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
      if (frm.doc.type == "Incoming") { //controlliamo che il messaggio sia in ingresso
        cur_frm.set_df_property("attach", "read_only", 1); //rendo readonly l'attachment dei files
        if (((frm.doc.message).split(":")[0]) == "media") { //controlliamo che il messaggio in ingresso sia un file multimediale
          var downloadButton = $('<button class="btn btn-default">Download File</button>');
          downloadButton.click(function() {
          var fileUrl = frappe.urllib.get_full_url(frappe.urllib.get_file_url("/files/" + ((frm.doc.message).split(":").pop())));
          window.open(fileUrl); //apre l'immagine scaricata in un'altra finestra
      });
      frm.page.add_inner_button(downloadButton[0].outerHTML);
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
  