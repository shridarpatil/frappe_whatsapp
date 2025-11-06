frappe.ui.form.on('Bulk WhatsApp Message', {
    refresh: function(frm) {
        // Add progress bar
        if(frm.doc.docstatus === 1 && frm.doc.status != 'Draft') {
            frm.add_custom_button(__('Check Progress'), function() {
                frappe.call({
                    method: 'frappe_whatsapp.utils.bulk_messaging.get_progress',
                    args: {
                        name: frm.doc.name
                    },
                    callback: function(r) {
                        if(r.message) {
                            let progress = r.message;
                            let html = `
                                <div class="progress" style="height: 20px;">
                                    <div class="progress-bar bg-success" role="progressbar" 
                                        style="width: ${progress.percent}%;" 
                                        aria-valuenow="${progress.percent}" 
                                        aria-valuemin="0" 
                                        aria-valuemax="100">
                                        ${Math.round(progress.percent)}%
                                    </div>
                                </div>
                                <div class="mt-2">
                                    <span class="badge badge-success">Sent: ${progress.sent}</span>
                                    <span class="badge badge-danger ml-2">Failed: ${progress.failed}</span>
                                    <span class="badge badge-warning ml-2">Queued: ${progress.queued}</span>
                                    <span class="badge badge-info ml-2">Total: ${progress.total}</span>
                                </div>
                            `;
                            
                            frappe.msgprint({
                                title: __('Message Progress'),
                                indicator: 'blue',
                                message: html
                            });
                        }
                    }
                });
            });
            
            // Add retry button
            frm.add_custom_button(__('Retry Failed Messages'), function() {
                frappe.call({
                    method: 'frappe_whatsapp.utils.bulk_messaging.retry_failed',
                    args: {
                        name: frm.doc.name
                    },
                    callback: function(r) {
                        if(r.message) {
                            frm.reload_doc();
                        }
                    }
                });
            }).addClass('btn-danger');
        }
    },
    validate: function(frm) {
        if(frm.doc.recipient_type == 'Individual' && (!frm.doc.recipients || frm.doc.recipients.length === 0)) {
            frappe.throw(__('Please add at least one recipient'));
            return false;
        }
        
        if(frm.doc.recipient_type == 'Recipient List' && !frm.doc.recipient_list) {
            frappe.throw(__('Please select a recipient list'));
            return false;
        }
        
        if(frm.doc.use_template && !frm.doc.template) {
            frappe.throw(__('Please select a template'));
            return false;
        }
        
        if(!frm.doc.use_template && !frm.doc.message_content) {
            frappe.throw(__('Please enter message content'));
            return false;
        }
        
        return true;
    }
});
