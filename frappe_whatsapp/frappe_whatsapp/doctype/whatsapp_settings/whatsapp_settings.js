frappe.ui.form.on('WhatsApp Settings', {
    refresh: function(frm) {
        frm.add_custom_button("Refresh Doctype", () => {
            lead_map_field(frm);
            frappe.msgprint("Doctype refreshed")
        });
    },
    lead_reference_doctype: function(frm) {
        lead_map_field(frm);
    }
});

frappe.ui.form.on('Whatsapp Lead Field Mapping', {
    lead_field_value: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (frm.field_map && row.lead_field_value) {
            row.doctype_field_type = frm.field_map[row.lead_field_value] || "Unknown";
            frm.refresh_field("whatsapp_lead_field_mapping");
        }
    }
});

function lead_map_field(frm) {
    if (!frm.doc.lead_reference_doctype) {
        frm.toggle_display('whatsapp_lead_field_mapping', 0);
        return;
    }

    frm.toggle_display('whatsapp_lead_field_mapping', 1);

    frappe.model.with_doctype(frm.doc.lead_reference_doctype, function() {
        let meta = frappe.get_meta(frm.doc.lead_reference_doctype);

        let field_map = {};
        meta.fields.forEach(f => {
            field_map[f.fieldname] = f.fieldtype;
        });

        // Get required and optional fields
        let required_fields = meta.fields.filter(f => f.reqd === 1).map(f => f.fieldname);
        let optional_fields = meta.fields.filter(f => f.reqd !== 1).map(f => f.fieldname);

        // Always include "executive" in required fields
        if (!required_fields.includes("executive")) {
            required_fields.push("executive");
            field_map["executive"] = "Link";
        }

        let whatsapp_field_options = { "first_name": "name", "contact_number": "contact_number" };

        if (frm.fields_dict.whatsapp_lead_field_mapping) {
            let grid = frm.fields_dict.whatsapp_lead_field_mapping.grid;

            if (grid) {
                frm.clear_table("whatsapp_lead_field_mapping");

                required_fields.forEach(fieldname => {
                    let child = frappe.model.add_child(frm.doc, "Whatsapp Lead Field Mapping", "whatsapp_lead_field_mapping");
                    child.lead_field_value = fieldname;
                    child.doctype_field_type = field_map[fieldname] || "Unknown";
                    child.whatsapp_field = whatsapp_field_options[fieldname] || "";
                });

                let df = frappe.meta.get_docfield("Whatsapp Lead Field Mapping", "lead_field_value", frm.doc.name);
                if (df) {
                    df.options = ["", ...required_fields, ...optional_fields].join("\n");
                }

                let whatsapp_df = frappe.meta.get_docfield("Whatsapp Lead Field Mapping", "whatsapp_field", frm.doc.name);
                if (whatsapp_df) {
                    whatsapp_df.options = ["", ...Object.values(whatsapp_field_options)].join("\n");
                }

                frm.refresh_field("whatsapp_lead_field_mapping");
            }
        }

        frm.field_map = field_map;
    });
}
