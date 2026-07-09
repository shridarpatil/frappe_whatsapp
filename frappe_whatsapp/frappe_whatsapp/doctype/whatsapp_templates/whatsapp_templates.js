// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Templates', {
	refresh(frm) {
		frm.add_custom_button(__('Preview'), () => show_template_preview(frm));

		// Approved templates are frozen by Meta, so only offer the builder for
		// ones that can still be changed.
		if (!frm.is_new() && (frm.doc.status || '').toUpperCase() !== 'APPROVED') {
			frm.add_custom_button(__('Edit in Builder'), () => {
				frappe.set_route('template-builder');
				// set_route drops the query string, so push it after navigating.
				setTimeout(() => {
					window.location.href = `/app/template-builder?name=${encodeURIComponent(frm.doc.name)}`;
				}, 0);
			});
		}
	},
});

/** Render the template the way WhatsApp will show it, in a dialog. */
function show_template_preview(frm) {
	const d = frm.doc;
	const samples = (d.sample_values || '').split(',').map((v) => v.trim());

	// {{1}}, {{2}}, ... -> sample values, keeping the token when none is set.
	const apply_samples = (text) =>
		(text || '').replace(/\{\{\s*(\d+)\s*\}\}/g, (full, n) => {
			const v = samples[Number(n) - 1];
			return v ? v : full;
		});

	// WhatsApp markup -> HTML. Escape first so template text can't inject HTML.
	const to_html = (text) => {
		let t = frappe.utils.escape_html(apply_samples(text));
		t = t.replace(/\*(.+?)\*/g, '<b>$1</b>');
		t = t.replace(/_(.+?)_/g, '<i>$1</i>');
		t = t.replace(/~(.+?)~/g, '<s>$1</s>');
		return t.replace(/\n/g, '<br>');
	};

	let header_html = '';
	if (d.header_type === 'TEXT' && d.header) {
		header_html = `<div class="wtb-bubble-header">${to_html(d.header)}</div>`;
	} else if (d.header_type === 'IMAGE' && d.sample) {
		header_html = `<div class="wtb-bubble-media"><img src="${frappe.utils.escape_html(d.sample)}" alt=""></div>`;
	} else if (d.header_type === 'DOCUMENT' && d.sample) {
		const file_name = decodeURIComponent(String(d.sample).split('/').pop());
		header_html = `<div class="wtb-bubble-doc">📄 ${frappe.utils.escape_html(file_name)}</div>`;
	}

	const footer_html = d.footer
		? `<div class="wtb-bubble-footer">${frappe.utils.escape_html(d.footer)}</div>`
		: '';

	const icon_for = (button_type) =>
		({ 'Visit Website': '🔗', 'Call Phone': '📞' }[button_type] || '↩');
	const buttons_html = (d.buttons || []).length
		? `<div class="wtb-wa-buttons">${(d.buttons || [])
				.map((b) => `<div class="wtb-wa-btn">${icon_for(b.button_type)} ${frappe.utils.escape_html(b.button_label || '')}</div>`)
				.join('')}</div>`
		: '';

	const account = d.whatsapp_account || 'WhatsApp';
	const dialog = new frappe.ui.Dialog({
		title: __('Template Preview'),
		size: 'small',
		fields: [{ fieldtype: 'HTML', fieldname: 'preview' }],
	});

	dialog.fields_dict.preview.$wrapper.html(`
		<div class="wtb-root" style="background:transparent; min-height:0; padding:0;">
			<div class="wtb-phone">
				<div class="wtb-phone-inner">
					<div class="wtb-wa-head">
						<span style="color:#8696a0; font-size:16px;">‹</span>
						<div class="wtb-wa-avatar">${frappe.utils.escape_html(account.charAt(0).toUpperCase())}</div>
						<div style="flex:1;">
							<div class="wtb-wa-name">${frappe.utils.escape_html(account)}</div>
							<div class="wtb-wa-sub">${__('Business account')}</div>
						</div>
					</div>
					<div class="wtb-wa-chat" style="min-height:220px;">
						<div class="wtb-wa-today"><span>${__('TODAY')}</span></div>
						<div class="wtb-bubble">
							${header_html}
							<div class="wtb-bubble-body">${to_html(d.template)}</div>
							${footer_html}
							<div class="wtb-bubble-time"><span>10:24 AM</span></div>
						</div>
						${buttons_html}
					</div>
				</div>
			</div>
			<p class="text-muted" style="margin-top:12px; font-size:11.5px; text-align:center;">
				${d.sample_values ? __('Sample values applied') : __('No sample values set — variables shown as placeholders')}
			</p>
		</div>
	`);

	dialog.show();
}
