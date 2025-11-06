frappe.ui.form.on('WhatsApp Recipient List', {
    refresh: function(frm) {
        frm.fields_dict.import_button.onclick = function() {
            if(!frm.doc.doctype_to_import || !frm.doc.mobile_field) {
                frappe.throw(__('Please select a DocType and Mobile Field before importing'));
                return;
            }
            
            let filters = null;
            if(frm.doc.import_filters) {
                try {
                    filters = JSON.parse(frm.doc.import_filters);
                } catch(e) {
                    frappe.throw(__('Invalid JSON in Filters field'));
                    return;
                }
            }
            
            frappe.call({
                method: 'frappe_whatsapp.utils.bulk_messaging.import_recipients',
                args: {
                    list_name: frm.doc.name,
                    doctype: frm.doc.doctype_to_import,
                    mobile_field: frm.doc.mobile_field,
                    name_field: frm.doc.name_field,
                    filters: filters,
                    limit: frm.doc.import_limit,
                    data_fields: frm.doc.data_fields
                },
                callback: function(r) {
                    if(r.message) {
                        frappe.msgprint(__(`${r.message} recipients imported successfully`));
                        frm.reload_doc();
                    }
                }
            });
        };
        
        // Add a button to add a test recipient
        frm.add_custom_button(__('Add Test Recipient'), function() {
            let d = new frappe.ui.Dialog({
                title: __('Add Test Recipient'),
                fields: [
                    {label: __('Mobile Number'), fieldname: 'mobile_number', fieldtype: 'Data', reqd: 1},
                    {label: __('Recipient Name'), fieldname: 'recipient_name', fieldtype: 'Data'},
                    {label: __('Recipient Data (JSON)'), fieldname: 'recipient_data', fieldtype: 'Code', options: 'JSON'}
                ],
                primary_action_label: __('Add'),
                primary_action: function(values) {
                    if(!values.mobile_number) {
                        frappe.throw(__('Mobile Number is required'));
                        return;
                    }
                    
                    // Validate JSON if provided
                    if(values.recipient_data) {
                        try {
                            JSON.parse(values.recipient_data);
                        } catch(e) {
                            frappe.throw(__('Invalid JSON in Recipient Data field'));
                            return;
                        }
                    }
                    
                    frm.add_child('recipients', {
                        mobile_number: values.mobile_number,
                        recipient_name: values.recipient_name,
                        recipient_data: values.recipient_data
                    });
                    
                    frm.refresh_field('recipients');
                    d.hide();
                    
                    frappe.show_alert({
                        message: __('Test recipient added'),
                        indicator: 'green'
                    });
                }
            });
            d.show();
        });
        
        // Add a button to validate all recipients
        frm.add_custom_button(__('Validate Recipients'), function() {
            let invalid = [];
            
            (frm.doc.recipients || []).forEach(function(row, idx) {
                let mobile = row.mobile_number || '';
                
                // Remove non-numeric characters except '+'
                mobile = mobile.replace(/[^\d+]/g, '');
                
                // Basic validation - should start with + or number and be at least 10 digits
                if(!/^(\+|[0-9])/.test(mobile) || mobile.replace(/\+/g, '').length < 10) {
                    invalid.push({
                        idx: idx + 1,
                        mobile: row.mobile_number,
                        reason: 'Invalid format'
                    });
                }
            });
            
            if(invalid.length) {
                let html = '<div class="text-danger">Found ' + invalid.length + ' invalid numbers:</div><table class="table table-bordered">';
                html += '<thead><tr><th>Row</th><th>Number</th><th>Reason</th></tr></thead><tbody>';
                
                invalid.forEach(function(row) {
                    html += '<tr><td>' + row.idx + '</td><td>' + row.mobile + '</td><td>' + row.reason + '</td></tr>';
                });
                
                html += '</tbody></table>';
                
                frappe.msgprint({
                    title: __('Validation Results'),
                    indicator: 'red',
                    message: html
                });
            } else {
                frappe.msgprint({
                    title: __('Validation Results'),
                    indicator: 'green',
                    message: __('All recipients have valid numbers')
                });
            }
        });
    }
});
