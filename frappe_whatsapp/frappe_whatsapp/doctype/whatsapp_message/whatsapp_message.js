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
        //notifico l'arrivo di un nuovo messaggio in ingresso specificando il mittente
        frappe.msgprint("Messaggio in arrivo da " + frm.doc.from, indicator="green", alert=True)
        if (((frm.doc.message).split(":")[0]) == "media") { //controlliamo che il messaggio in ingresso sia un file multimediale
          
          var fileUrl = frappe.urllib.get_full_url(frappe.urllib.get_file_url("/files/" + ((frm.doc.message).split(":").pop())));
          frappe.msgprint(fileUrl, indicator="green", alert=True)
       //   var fileData = {
        //    file_url: fileUrl,
        //    file_name: frappe.get_file_name(fileUrl)
       //   };

         // frappe.upload.upload_file(fileData)
          // .then(function(attachment) {
            // Il file è stato allegato con successo
           //  var doc = cur_frm.doc; // Riferimento al documento corrente
           //  doc.attachment = attachment.file_url; // Imposta il campo di allegato
           //  cur_frm.refresh_field("attachment"); // Aggiorna il campo nel form
           // })
           // .catch(function(error) {
            // Si è verificato un errore durante l'allegato del file
           // console.error(error);
         //   });
          

          // window.open(fileUrl); //apre l'immagine scaricata in un'altra finestra

        }
      }
      
      //bottone per rispondere alle domande
      frm.add_custom_button(__('rispondi al messaggio'), function(){
        // Apertura di un nuovo documento "WhatsApp Message" con il campo "a" selezionato sul nome del mittente
        var newDoc = frappe.model.get_new_doc("WhatsApp Message");
        newDoc.a = customerName;
        frappe.set_route("Form", "WhatsApp Message", newDoc.name);
      }, __("rispondi"));

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
  