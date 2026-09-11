/**
 * WhatsApp Template Builder — visual, drag-and-drop desk page.
 *
 * Renders a 3-panel builder (component palette · canvas · live WhatsApp
 * preview) over the existing "WhatsApp Templates" DocType. On save it calls
 * the whitelisted `save_template` endpoint, which creates/updates the DocType
 * doc; the DocType controller performs the Meta round-trip.
 *
 * Open a new template at  /app/template-builder
 * Edit an existing one at  /app/template-builder?name=<template-name>
 *
 * Vanilla JS only — no framework, no build step. Drag/drop uses the
 * framework-bundled Sortable when available and degrades gracefully.
 */

frappe.pages['template-builder'].on_page_load = function (wrapper) {
	frappe.require('/assets/frappe_whatsapp/css/template_builder.css');
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Template Builder',
		single_column: true,
	});
	new TemplateBuilder(page);
};

const WA = {
	BODY_MAX: 1024,
	HEADER_MAX: 60,
	FOOTER_MAX: 60,
	MAX_BUTTONS: 10,
	API: 'frappe_whatsapp.frappe_whatsapp.page.template_builder.template_builder',
};

class TemplateBuilder {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.editName = frappe.utils.get_url_arg('name') || null;
		this.doctypeFields = []; // for the For-DocType variable mapping
		this.state = this.blankState();
		this.boot = { categories: [], languages: [], accounts: [], has_account: false, header_types: ['TEXT', 'IMAGE', 'DOCUMENT'] };
		this.saving = false;
		this.init();
	}

	blankState() {
		return {
			template_name: '',
			category: 'UTILITY',
			language: 'en',
			whatsapp_account: null,
			for_doctype: '',
			components: { header: false, body: true, footer: false, buttons: false },
			header: { type: 'TEXT', text: '', sample: '' },
			body: 'Hi {{1}}, welcome!',
			footer: '',
			buttons: [],
			samples: {}, // { "1": "Rahul" }
			fields: {},  // { "1": "customer_name" }  (maps to field_names)
			status: null,
			has_meta_id: false,
			locked: false,
		};
	}

	async init() {
		this.$body.html(`<div class="wtb-root"><div class="text-muted" style="padding:40px 28px;">${__('Loading builder…')}</div></div>`);
		try {
			this.boot = await frappe.call(`${WA.API}.get_boot`).then((r) => r.message);
		} catch (e) {
			this.boot = { categories: ['UTILITY', 'MARKETING', 'AUTHENTICATION'], header_types: ['TEXT', 'IMAGE', 'DOCUMENT'], languages: [{ name: 'en', language_name: 'English' }], accounts: [], has_account: false };
		}
		if (this.boot.default_account) this.state.whatsapp_account = this.boot.default_account;

		try {
			this.doctypeList = await frappe.call({
				method: 'frappe.client.get_list',
				args: { doctype: 'DocType', fields: ['name'], filters: { istable: 0, issingle: 0 }, limit_page_length: 0 },
			}).then((r) => (r.message || []).map((d) => d.name));
		} catch (e) {
			this.doctypeList = [];
		}

		if (this.editName) {
			try {
				const loaded = await frappe.call(`${WA.API}.load_template`, { name: this.editName }).then((r) => r.message);
				this.hydrate(loaded);
			} catch (e) {
				frappe.show_alert({ message: __('Could not load template {0}', [this.editName]), indicator: 'red' });
				this.editName = null;
			}
		}
		if (this.state.for_doctype) await this.loadDoctypeFields(this.state.for_doctype);
		this.render();
	}

	/** Map a loaded template (server shape) into builder state. */
	hydrate(d) {
		const s = this.blankState();
		s.template_name = d.template_name || '';
		s.category = d.category || 'UTILITY';
		s.language = d.language || 'en';
		s.whatsapp_account = d.whatsapp_account || this.boot.default_account || null;
		s.for_doctype = d.for_doctype || '';
		s.body = d.body || '';
		s.footer = d.footer || '';
		s.header = { type: (d.header && d.header.type) || 'TEXT', text: (d.header && d.header.text) || '', sample: (d.header && d.header.sample) || '' };
		// `unsupported` must survive hydration: it drives the button-row badge
		// and blocks duplicating a template the builder cannot round-trip.
		s.buttons = (d.buttons || []).map((b) => ({ kind: b.kind, label: b.label || '', url: b.url || '', phone_number: b.phone_number || '', example: b.example || '', unsupported: !!b.unsupported }));
		s.status = d.status || null;
		s.has_meta_id = !!d.has_meta_id;
		s.locked = !!d.locked;

		const vars = this.detectVars(s.body);
		(d.sample_values || []).forEach((v, i) => { if (vars[i] != null) s.samples[vars[i]] = v; });
		(d.field_names || []).forEach((v, i) => { if (vars[i] != null) s.fields[vars[i]] = v; });

		s.components = {
			header: !!(s.header.text || s.header.sample),
			body: true,
			footer: !!s.footer,
			buttons: s.buttons.length > 0,
		};
		this.state = s;
	}

	async loadDoctypeFields(doctype) {
		if (!doctype) { this.doctypeFields = []; return; }
		try {
			this.doctypeFields = await frappe.call(`${WA.API}.get_doctype_fields`, { doctype }).then((r) => r.message || []);
		} catch (e) {
			this.doctypeFields = [];
		}
	}

	/** Fetch a sample value for one mapped variable from the latest record. */
	async fillSampleFromField(varNo, fieldname) {
		if (!this.state.for_doctype || !fieldname) return;
		try {
			const res = await frappe.call(`${WA.API}.get_sample_record`, {
				doctype: this.state.for_doctype, fieldnames: [fieldname],
			}).then((r) => r.message);
			if (res && res.record && res.values && res.values[fieldname] !== undefined) {
				this.state.samples[varNo] = String(res.values[fieldname] || '');
				this.render();
				frappe.show_alert({ message: __('Sample filled from {0}', [res.record]), indicator: 'blue' }, 3);
			} else if (res && !res.record) {
				frappe.show_alert({ message: __('No records found in {0}', [this.state.for_doctype]), indicator: 'orange' }, 3);
			}
		} catch (e) {
			console.error(e);
		}
	}

	/** Fetch sample values for every mapped variable in one call. */
	async fillAllSamplesFromFields() {
		const vars = this.detectVars(this.state.body);
		const mapped = vars.filter((n) => this.fieldFor(n));
		if (!this.state.for_doctype || !mapped.length) {
			frappe.show_alert({ message: __('Map at least one variable to a field first'), indicator: 'orange' }, 3);
			return;
		}
		frappe.dom.freeze(__('Fetching sample data…'));
		try {
			const fieldnames = mapped.map((n) => this.fieldFor(n));
			const res = await frappe.call(`${WA.API}.get_sample_record`, {
				doctype: this.state.for_doctype, fieldnames,
			}).then((r) => r.message);
			if (res && res.record) {
				mapped.forEach((n) => {
					const fn = this.fieldFor(n);
					if (res.values[fn] !== undefined) this.state.samples[n] = String(res.values[fn] || '');
				});
				this.render();
				frappe.show_alert({ message: __('Samples filled from {0}', [res.record]), indicator: 'green' }, 4);
			} else {
				frappe.show_alert({ message: __('No records found in {0}', [this.state.for_doctype]), indicator: 'orange' }, 3);
			}
		} catch (e) {
			console.error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	/* ---------------- variable helpers ---------------- */

	detectVars(text) {
		const set = [];
		const re = /\{\{\s*(\d+)\s*\}\}/g;
		let m;
		while ((m = re.exec(text || '')) !== null) if (!set.includes(m[1])) set.push(m[1]);
		return set.sort((a, b) => Number(a) - Number(b));
	}

	nextVarIndex() {
		const vars = this.detectVars(this.state.body).map(Number);
		return vars.length ? Math.max(...vars) + 1 : 1;
	}

	sampleFor(idx) { return this.state.samples[idx] != null ? this.state.samples[idx] : ''; }
	fieldFor(idx) { return this.state.fields[idx] != null ? this.state.fields[idx] : ''; }

	applySamples(text) {
		return (text || '').replace(/\{\{\s*(\d+)\s*\}\}/g, (_full, n) => {
			const v = this.sampleFor(n);
			return v !== '' ? v : `{{${n}}}`;
		});
	}

	waMarkupToHtml(text) {
		let t = frappe.utils.escape_html(text || '');
		t = t.replace(/\*(.+?)\*/g, '<b>$1</b>');
		t = t.replace(/_(.+?)_/g, '<i>$1</i>');
		t = t.replace(/~(.+?)~/g, '<s>$1</s>');
		return t.replace(/\n/g, '<br>');
	}

	/* ---------------- render ---------------- */

	render() {
		this.$body.html(`
			<div class="wtb-root">
				${this.renderHeader()}
				<div class="wtb-workspace">
					${this.renderPalette()}
					<div class="wtb-canvas">${this.renderCanvas()}</div>
					${this.renderPreview()}
				</div>
			</div>
		`);
		this.bind();
		this.applyLock();
	}

	/** An approved template is read-only: freeze every editing control. */
	applyLock() {
		if (!this.state.locked) return;
		const $root = this.$body.find('.wtb-root');
		$root.addClass('is-locked');
		$root.find('input, textarea, select').prop('disabled', true);
		// Structural controls (palette, add/remove, toolbar) are inert too.
		$root.find('[data-add], [data-addbtn], [data-remove], [data-btnremove], [data-wrap], [data-emoji], [data-addvar], [data-htype], [data-media-upload], [data-media-remove], [data-fill-all]')
			.addClass('is-disabled')
			.off('click');
	}

	renderHeader() {
		const editing = !!this.editName;
		const pushed = this.state.has_meta_id;
		const locked = this.state.locked;
		const badge = editing
			? `<span class="wtb-badge ${this.statusBadgeClass()}">${frappe.utils.escape_html(this.state.status || 'Pending')}</span>`
			: `<span class="wtb-badge is-pending">${__('Draft')}</span>`;
		// Sync only makes sense once the template exists on Meta.
		const syncBtn = editing && pushed
			? `<button class="wtb-icon-act" data-act="sync" title="${__('Refresh status from Meta')}">↻</button>`
			: '';
		const deleteBtn = editing
			? `<button class="wtb-icon-act wtb-icon-danger" data-act="delete" title="${__('Delete template')}">🗑</button>`
			: '';
		// A template that already exists on Meta is view-only (Meta does not
		// allow re-editing submitted templates): offer read-only + "duplicate"
		// instead of Save/Submit, which the server would reject anyway.
		const saveActions = locked
			? `<button class="wtb-btn wtb-btn-primary" data-act="duplicate">⧉ ${__('Duplicate as New')}</button>`
			: `<button class="wtb-btn" data-act="save-draft">${__('Save Draft')}</button>
			   <button class="wtb-btn wtb-btn-primary" data-act="submit"><span>✓</span> ${__('Submit to Meta')}</button>`;
		const subtitle = locked
			? __('Already submitted to Meta. Templates on Meta cannot be edited, duplicate it to make changes.')
			: (editing ? __('Editing {0}', [frappe.utils.escape_html(this.editName)]) : __('Build a Meta-approved WhatsApp message template visually.'));
		return `
			<div class="wtb-pagehead">
				<div>
					<div class="wtb-title-row">
						<h1>${editing ? __('Edit Template') : __('Template Builder')}</h1>
						${badge}
						${syncBtn}
					</div>
					<p class="wtb-subtitle ${locked ? 'is-locked' : ''}">${subtitle}</p>
				</div>
				<div class="wtb-actions">
					<button class="wtb-btn wtb-btn-ghost" data-act="new">+ ${__('New')}</button>
					<button class="wtb-btn wtb-btn-ghost" data-act="open">${__('Open…')}</button>
					${deleteBtn}
					<span class="wtb-actions-sep"></span>
					${saveActions}
				</div>
			</div>`;
	}

	statusBadgeClass() {
		const st = (this.state.status || '').toUpperCase();
		if (st === 'APPROVED') return 'is-approved';
		if (st === 'REJECTED') return 'is-rejected';
		return 'is-pending';
	}

	renderPalette() {
		const added = this.state.components;
		const item = (key, icon, iconBg, iconColor, title, sub) => `
			<div class="wtb-palette-item ${added[key] ? 'is-added' : ''}" data-add="${key}">
				<span class="wtb-grip">⠿</span>
				<div class="wtb-pi-icon" style="background:${iconBg}; color:${iconColor};">${icon}</div>
				<div><div class="wtb-pi-title">${title}</div><div class="wtb-pi-sub">${sub}</div></div>
			</div>`;
		const btnType = (kind, label) => `<div class="wtb-btntype" data-addbtn="${kind}"><span class="wtb-grip">⠿</span> ${label}</div>`;
		return `
			<div class="wtb-card wtb-palette">
				<div class="wtb-eyebrow">${__('Components')}</div>
				<p class="wtb-hint">${__('Click or drag a block onto the canvas')}</p>
				<div class="wtb-palette-list">
					${item('header', '▭', '#e8f7ee', '#1f9d55', __('Header'), __('Text · Media'))}
					${item('body', '≡', '#eaf2fd', '#2477d4', __('Body'), __('Required'))}
					${item('footer', '▁', '#f3eefb', '#7b4fc9', __('Footer'), __('Optional'))}
					${item('buttons', '⬒', '#fdeeef', '#d24b58', __('Buttons'), __('Up to 10'))}
				</div>
				<div class="wtb-divider"></div>
				<div class="wtb-eyebrow" style="margin-bottom:10px;">${__('Button types')}</div>
				<div class="wtb-btntypes">
					${btnType('quick_reply', __('Quick reply'))}
					${btnType('url', __('Visit website'))}
					${btnType('phone', __('Call phone number'))}
				</div>
			</div>`;
	}

	renderCanvas() {
		const parts = [this.renderSettings()];
		if (this.state.components.header) parts.push(this.renderHeaderBlock());
		if (this.state.components.body) parts.push(this.renderBodyBlock());
		if (this.state.components.body && this.detectVars(this.state.body).length) parts.push(this.renderSamples());
		if (this.state.components.footer) parts.push(this.renderFooterBlock());
		if (this.state.components.buttons) parts.push(this.renderButtonsBlock());
		parts.push(`<div class="wtb-drophint" data-drop>${__('Click a component in the palette to add it')}</div>`);
		return parts.join('');
	}

	renderSettings() {
		const s = this.state;
		const cats = (this.boot.categories || []).map((c) => `<option value="${c}" ${s.category === c ? 'selected' : ''}>${frappe.utils.to_title_case(c.toLowerCase())}</option>`).join('');
		const langs = (this.boot.languages || []).map((l) => `<option value="${l.name}" ${s.language === l.name ? 'selected' : ''}>${frappe.utils.escape_html(l.language_name || l.name)} (${l.name})</option>`).join('');
		const accts = [`<option value="">${__('— Select account —')}</option>`]
			.concat((this.boot.accounts || []).map((a) => `<option value="${a.name}" ${s.whatsapp_account === a.name ? 'selected' : ''}>${frappe.utils.escape_html(a.name)}${a.is_default_outgoing ? ' ' + __('(default)') : ''}</option>`))
			.join('');
		return `
			<div class="wtb-card wtb-settings">
				<div class="wtb-settings-grid">
					<div class="wtb-field">
						<label>${__('Template Name')}</label>
						<input class="wtb-input" data-field="template_name" placeholder="order_confirmation_v2" value="${frappe.utils.escape_html(s.template_name)}" ${this.editName ? 'readonly' : ''}>
					</div>
					<div class="wtb-field">
						<label>${__('Category')}</label>
						<select class="wtb-select" data-field="category">${cats}</select>
					</div>
					<div class="wtb-field">
						<label>${__('Language')}</label>
						<select class="wtb-select" data-field="language">${langs}</select>
					</div>
				</div>
				<div class="wtb-settings-grid" style="margin-top:14px;">
					<div class="wtb-field">
						<label>${__('WhatsApp Account')}</label>
						<select class="wtb-select" data-field="whatsapp_account">${accts}</select>
					</div>
					<div class="wtb-field">
						<label>${__('For DocType')} <span class="wtb-tag">${__('optional')}</span></label>
						<input class="wtb-input" data-field="for_doctype" data-doctype-link placeholder="${__('e.g. Sales Invoice')}" value="${frappe.utils.escape_html(s.for_doctype || '')}">
					</div>
					<div class="wtb-field"></div>
				</div>
			</div>`;
	}

	renderHeaderBlock() {
		const h = this.state.header;
		const seg = (this.boot.header_types || ['TEXT', 'IMAGE', 'DOCUMENT'])
			.map((t) => `<button class="wtb-seg-item ${h.type === t ? 'is-active' : ''}" data-htype="${t}">${frappe.utils.to_title_case(t.toLowerCase())}</button>`)
			.join('');
		let inner;
		if (h.type === 'TEXT') {
			const len = (h.text || '').length;
			inner = `
				<input class="wtb-input" data-field="header_text" maxlength="${WA.HEADER_MAX}" placeholder="${__('Header text')}" value="${frappe.utils.escape_html(h.text)}">
				<div class="wtb-meta-row"><span>${__('Text header, no variables')}</span><span class="${len > WA.HEADER_MAX ? 'is-over' : ''}">${len} / ${WA.HEADER_MAX}</span></div>`;
		} else {
			inner = `
				<div class="wtb-media">
					${h.sample
						? `<div class="wtb-media-file"><span class="wtb-media-name">${frappe.utils.escape_html(this.fileName(h.sample))}</span><button class="wtb-icon-btn" data-media-remove title="${__('Remove')}">🗑</button></div>`
						: ''}
					<button class="wtb-btn" data-media-upload>↑ ${h.sample ? __('Replace file') : __('Upload {0}', [frappe.utils.to_title_case(h.type.toLowerCase())])}</button>
					<div class="wtb-meta-row"><span>${__('Uploaded to Meta on submit')}</span></div>
				</div>`;
		}
		return `
			<div class="wtb-block" data-block="header">
				<div class="wtb-block-head">
					<div class="wtb-block-head-left"><span class="wtb-grip" style="cursor:grab;">⠿</span><span class="wtb-block-title">${__('Header')}</span><span class="wtb-tag">${__('Optional')}</span></div>
					<div class="wtb-block-actions"><button class="wtb-icon-btn" data-remove="header" title="${__('Remove')}">🗑</button></div>
				</div>
				<div class="wtb-block-body">
					<div class="wtb-seg">${seg}</div>
					${inner}
				</div>
			</div>`;
	}

	fileName(url) {
		if (!url) return '';
		try { return decodeURIComponent(url.split('/').pop().split('?')[0]); } catch (e) { return url; }
	}

	renderBodyBlock() {
		const body = this.state.body;
		const vars = this.detectVars(body);
		const len = body.length;
		return `
			<div class="wtb-block is-required" data-block="body">
				<div class="wtb-block-head">
					<div class="wtb-block-head-left"><span class="wtb-grip" style="cursor:grab;">⠿</span><span class="wtb-block-title">${__('Body')}</span><span class="wtb-pill">${__('REQUIRED')}</span></div>
					<div class="wtb-block-actions"></div>
				</div>
				<div class="wtb-block-body">
					<div class="wtb-toolbar">
						<span class="wtb-tool wtb-tool-b" data-wrap="*" title="${__('Bold')}">B</span>
						<span class="wtb-tool wtb-tool-i" data-wrap="_" title="${__('Italic')}">I</span>
						<span class="wtb-tool wtb-tool-s" data-wrap="~" title="${__('Strikethrough')}">S</span>
						<span class="wtb-tool" data-emoji title="${__('Emoji')}">😊</span>
						<div class="wtb-tool-sep"></div>
						<span class="wtb-addvar" data-addvar>+ ${__('Add variable')}</span>
					</div>
					<textarea class="wtb-texted wtb-body-texted" data-field="body">${frappe.utils.escape_html(body)}</textarea>
					<div class="wtb-meta-row"><span>${vars.length} ${__('variables detected')}</span><span class="${len > WA.BODY_MAX ? 'is-over' : ''}">${len} / ${WA.BODY_MAX}</span></div>
				</div>
			</div>`;
	}

	renderSamples() {
		const vars = this.detectVars(this.state.body);
		const hasDoctype = !!this.state.for_doctype;
		const fieldOptions = this.doctypeFields || [];
		const mappingCell = (n) => {
			if (!hasDoctype) return '';
			const opts = [`<option value="">${__('— map field —')}</option>`]
				.concat(fieldOptions.map((f) => `<option value="${frappe.utils.escape_html(f.value)}" ${this.fieldFor(n) === f.value ? 'selected' : ''}>${frappe.utils.escape_html(f.label)}</option>`))
				.join('');
			return `<select class="wtb-select wtb-mapfield" data-field-map="${n}">${opts}</select>`;
		};
		const rows = vars.map((n) => `
			<div class="wtb-sample-row">
				<span class="wtb-varchip">{{${n}}}</span>
				<input class="wtb-input" data-sample="${n}" placeholder="${__('Sample value')}" value="${frappe.utils.escape_html(this.sampleFor(n))}">
				${mappingCell(n)}
			</div>`).join('');
		const anyMapped = hasDoctype && vars.some((n) => this.fieldFor(n));
		const fillBtn = anyMapped
			? `<button class="wtb-btn wtb-btn-mini" data-fill-all title="${__('Fetch values from the latest {0} record', [frappe.utils.escape_html(this.state.for_doctype)])}">⬇ ${__('Fill from record')}</button>`
			: '';
		return `
			<div class="wtb-card wtb-card-pad">
				<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
					<span class="wtb-block-title">${__('Sample Values')}</span>
					<span class="wtb-tag">${hasDoctype ? __('Sample for Meta · Field for real data') : __('Used for Meta review & preview')}</span>
					<span style="flex:1;"></span>
					${fillBtn}
				</div>
				<p class="wtb-hint" style="margin:0 0 13px;">${hasDoctype ? __('Map each variable to a {0} field to auto-fill at send time.', [frappe.utils.escape_html(this.state.for_doctype)]) : __('Set a "For DocType" above to map variables to real fields.')}</p>
				<div class="wtb-sample-rows">${rows}</div>
			</div>`;
	}

	renderFooterBlock() {
		const f = this.state.footer;
		return `
			<div class="wtb-block" data-block="footer">
				<div class="wtb-block-head">
					<div class="wtb-block-head-left"><span class="wtb-grip" style="cursor:grab;">⠿</span><span class="wtb-block-title">${__('Footer')}</span><span class="wtb-tag">${__('Optional')}</span></div>
					<div class="wtb-block-actions"><button class="wtb-icon-btn" data-remove="footer" title="${__('Remove')}">🗑</button></div>
				</div>
				<div class="wtb-block-body">
					<input class="wtb-input" data-field="footer" maxlength="${WA.FOOTER_MAX}" placeholder="${__('Reply STOP to unsubscribe')}" value="${frappe.utils.escape_html(f)}">
				</div>
			</div>`;
	}

	renderButtonsBlock() {
		const rows = this.state.buttons.map((b, i) => this.renderButtonRow(b, i)).join('');
		const count = this.state.buttons.length;
		return `
			<div class="wtb-block" data-block="buttons">
				<div class="wtb-block-head">
					<div class="wtb-block-head-left"><span class="wtb-grip" style="cursor:grab;">⠿</span><span class="wtb-block-title">${__('Buttons')}</span><span class="wtb-tag">${count} ${__('of')} ${WA.MAX_BUTTONS}</span></div>
					<div class="wtb-block-actions"><button class="wtb-icon-btn" data-remove="buttons" title="${__('Remove')}">🗑</button></div>
				</div>
				<div class="wtb-block-body wtb-btn-rows">
					${rows}
					<button class="wtb-add-btn" data-addbtn="quick_reply">+ ${__('Add button')}</button>
				</div>
			</div>`;
	}

	renderButtonRow(b, i) {
		const kindMeta = b.unsupported
			? { cls: 'k-reply', label: b.kind || __('UNSUPPORTED') }
			: ({
				quick_reply: { cls: 'k-reply', label: __('REPLY') },
				url: { cls: 'k-url', label: __('VISIT SITE') },
				phone: { cls: 'k-call', label: __('CALL') },
			}[b.kind] || { cls: 'k-reply', label: b.kind });
		let fields = `<input class="wtb-input" data-btnfield="label" data-i="${i}" placeholder="${__('Button text')}" value="${frappe.utils.escape_html(b.label || '')}">`;
		if (b.kind === 'url') {
			fields += `<input class="wtb-input" data-btnfield="url" data-i="${i}" placeholder="https://…/{{1}}" value="${frappe.utils.escape_html(b.url || '')}">`;
			if (b.url && b.url.includes('{{')) {
				fields += `<input class="wtb-input" data-btnfield="example" data-i="${i}" placeholder="${__('URL Example (e.g. https://example.com/orders/123)')}" value="${frappe.utils.escape_html(b.example || '')}">`;
			}
		} else if (b.kind === 'phone') {
			fields += `<input class="wtb-input" data-btnfield="phone_number" data-i="${i}" placeholder="+91 80 0000 0000" value="${frappe.utils.escape_html(b.phone_number || '')}">`;
		}
		return `
			<div class="wtb-btn-row">
				<span class="wtb-grip" style="cursor:grab;">⠿</span>
				<span class="wtb-btn-kind ${kindMeta.cls}">${kindMeta.label}</span>
				<div class="wtb-btn-fields">${fields}</div>
				<button class="wtb-icon-btn" data-btnremove="${i}" title="${__('Remove')}">🗑</button>
			</div>`;
	}

	renderPreview() {
		const s = this.state;
		const acct = s.whatsapp_account || 'WhatsApp';
		const initial = (acct || 'W').trim().charAt(0).toUpperCase();
		let headerHtml = '';
		if (s.components.header && s.header.type === 'TEXT' && s.header.text) {
			headerHtml = `<div class="wtb-bubble-header">${this.waMarkupToHtml(this.applySamples(s.header.text))}</div>`;
		} else if (s.components.header && s.header.sample && s.header.type === 'IMAGE') {
			headerHtml = `<div class="wtb-bubble-media"><img src="${frappe.utils.escape_html(s.header.sample)}" alt=""></div>`;
		} else if (s.components.header && s.header.sample && s.header.type === 'DOCUMENT') {
			headerHtml = `<div class="wtb-bubble-doc">📄 ${frappe.utils.escape_html(this.fileName(s.header.sample))}</div>`;
		}
		const bodyText = `<div class="wtb-bubble-body">${this.waMarkupToHtml(this.applySamples(s.body))}</div>`;
		const footerText = s.components.footer && s.footer ? `<div class="wtb-bubble-footer">${frappe.utils.escape_html(this.applySamples(s.footer))}</div>` : '';
		const btns = (s.components.buttons ? s.buttons : []).filter((b) => b.label).map((b) => {
			const icon = b.kind === 'url' ? '🔗' : b.kind === 'phone' ? '📞' : '↩';
			return `<div class="wtb-wa-btn">${icon} ${frappe.utils.escape_html(b.label)}</div>`;
		}).join('');
		const btnBlock = btns ? `<div class="wtb-wa-buttons">${btns}</div>` : '';
		return `
			<div class="wtb-preview">
				<div class="wtb-preview-head">
					<span class="wtb-eyebrow">${__('Live Preview')}</span>
					<span class="wtb-note">${__('Sample values applied')}</span>
				</div>
				<div class="wtb-phone">
					<div class="wtb-phone-inner">
						<div class="wtb-wa-head">
							<span style="color:#8696a0; font-size:16px;">‹</span>
							<div class="wtb-wa-avatar">${initial}</div>
							<div style="flex:1;"><div class="wtb-wa-name">${frappe.utils.escape_html(acct)}</div><div class="wtb-wa-sub">${__('Business account')}</div></div>
							<span style="color:#8696a0; font-size:14px;">⋮</span>
						</div>
						<div class="wtb-wa-chat">
							<div class="wtb-wa-today"><span>${__('TODAY')}</span></div>
							<div class="wtb-bubble">
								${headerHtml}
								${bodyText}
								${footerText}
								<div class="wtb-bubble-time"><span>10:24 AM</span></div>
							</div>
							${btnBlock}
						</div>
					</div>
				</div>
				${this.renderCompliance()}
			</div>`;
	}

	renderCompliance() {
		const checks = this.complianceChecks();
		const allOk = checks.every((c) => c.ok);
		const rows = checks.map((c) => `<div class="wtb-check ${c.ok ? 'ok' : 'bad'}"><span class="mark">${c.ok ? '✓' : '○'}</span> ${c.label}</div>`).join('');
		return `
			<div class="wtb-card wtb-compliance">
				<div class="wtb-compliance-head">
					<span class="wtb-block-title">${__('Meta compliance')}</span>
					<span class="wtb-status ${allOk ? 'ok' : 'bad'}">${allOk ? __('Ready to submit') : __('Needs attention')}</span>
				</div>
				<div class="wtb-checks">${rows}</div>
			</div>`;
	}

	isContiguousVars(vars) {
		if (!vars || !vars.length) return true;
		const nums = vars.map(Number);
		for (let i = 0; i < nums.length; i++) {
			if (nums[i] !== i + 1) return false;
		}
		return true;
	}

	complianceChecks() {
		const s = this.state;
		const vars = this.detectVars(s.body);
		const allSamples = vars.every((n) => this.sampleFor(n) !== '');
		const nameOk = /^[a-z0-9_]+$/.test((s.template_name || '').trim());
		const contiguousOk = this.isContiguousVars(vars);
		return [
			{ label: __('Template name is valid'), ok: nameOk },
			{ label: __('Body present & within limit'), ok: !!s.body.trim() && s.body.length <= WA.BODY_MAX },
			{ label: __('Variables numbered consecutively starting at {{1}}'), ok: contiguousOk },
			{ label: __('All variables have samples'), ok: allSamples },
			{ label: __('WhatsApp account selected'), ok: !!s.whatsapp_account },
		];
	}

	/* ---------------- event binding ---------------- */

	bind() {
		const self = this;
		const root = this.$body;

		root.find('[data-add]').on('click', function () {
			const key = $(this).data('add');
			self.state.components[key] = true;
			if (key === 'buttons' && !self.state.buttons.length) self.addButton('quick_reply');
			self.render();
		});

		root.find('[data-addbtn]').on('click', function () {
			self.state.components.buttons = true;
			self.addButton($(this).data('addbtn'));
			self.render();
		});

		root.find('[data-htype]').on('click', function () {
			self.state.header.type = $(this).data('htype');
			self.render();
		});

		root.find('[data-media-upload]').on('click', () => self.openFileUpload());
		root.find('[data-media-remove]').on('click', () => { self.state.header.sample = ''; self.render(); });

		root.find('[data-remove]').on('click', function () {
			const key = $(this).data('remove');
			self.state.components[key] = false;
			if (key === 'buttons') self.state.buttons = [];
			if (key === 'header') self.state.header = { type: 'TEXT', text: '', sample: '' };
			self.render();
		});

		root.find('[data-field]').on('input change', function () {
			const f = $(this).data('field');
			const val = $(this).val();
			if (f === 'template_name') { self.state.template_name = val; self.softRefreshCompliance(); }
			else if (f === 'category') { self.state.category = val; self.softRefreshPreview(); }
			else if (f === 'language') { self.state.language = val; }
			else if (f === 'whatsapp_account') { self.state.whatsapp_account = val; self.softRefreshPreview(); }
			else if (f === 'header_text') { self.state.header.text = val; self.updateHeaderCount(val); self.softRefreshPreview(); }
			else if (f === 'footer') { self.state.footer = val; self.softRefreshPreview(); }
			else if (f === 'body') { self.onBodyInput(val); }
			else if (f === 'for_doctype') { /* handled by the link control below */ }
		});

		// "For DocType" as a proper Link control (autocomplete of DocTypes).
		this.attachDoctypeLink();

		root.find('[data-sample]').on('input', function () {
			self.state.samples[String($(this).data('sample'))] = $(this).val();
			self.softRefreshPreview();
		});
		root.find('[data-field-map]').on('change', function () {
			const n = String($(this).data('field-map'));
			const fieldname = $(this).val();
			self.state.fields[n] = fieldname;
			if (fieldname) self.fillSampleFromField(n, fieldname);
		});
		root.find('[data-fill-all]').on('click', () => self.fillAllSamplesFromFields());

		root.find('[data-wrap]').on('click', function () { self.wrapSelection($(this).data('wrap')); });
		root.find('[data-emoji]').on('click', function () { self.insertAtCursor('😊'); self.softRefreshPreview(); });
		root.find('[data-addvar]').on('click', function () { self.insertAtCursor(`{{${self.nextVarIndex()}}}`); self.render(); });

		root.find('[data-btnfield]').on('input', function () {
			const i = $(this).data('i');
			self.state.buttons[i][$(this).data('btnfield')] = $(this).val();
			self.softRefreshPreview();
		});
		root.find('[data-btnremove]').on('click', function () {
			self.state.buttons.splice($(this).data('btnremove'), 1);
			self.render();
		});

		root.find('[data-act="save-draft"]').on('click', () => self.save(false));
		root.find('[data-act="submit"]').on('click', () => self.save(true));
		root.find('[data-act="new"]').on('click', () => self.newTemplate());
		root.find('[data-act="open"]').on('click', () => self.openTemplateDialog());
		root.find('[data-act="delete"]').on('click', () => self.deleteTemplate());
		root.find('[data-act="sync"]').on('click', () => self.syncStatus());
		root.find('[data-act="duplicate"]').on('click', () => self.duplicateTemplate());

		this.enableDnD();
	}

	/** Turn the For-DocType text input into a Frappe Link-style autocomplete. */
	attachDoctypeLink() {
		const self = this;
		const $inp = this.$body.find('[data-doctype-link]');
		if (!$inp.length) return;
		$inp.off('change blur').on('change blur', async function () {
			const val = ($(this).val() || '').trim();
			if (val === self.state.for_doctype) return;
			self.state.for_doctype = val;
			await self.loadDoctypeFields(val);
			self.render();
		});
		if (window.Awesomplete && $inp.get(0) && !$inp.data('awesomplete-attached')) {
			new window.Awesomplete($inp.get(0), { list: this.doctypeList || [], minChars: 1, maxItems: 15, autoFirst: true });
			$inp.data('awesomplete-attached', true);
		}
	}

	openFileUpload() {
		const self = this;
		const isImage = this.state.header.type === 'IMAGE';
		new frappe.ui.FileUploader({
			folder: 'Home/Attachments',
			restrictions: {
				allowed_file_types: isImage ? ['image/*'] : ['application/pdf', '.pdf'],
			},
			make_attachments_public: true,
			on_success: (file_doc) => {
				self.state.header.sample = file_doc.file_url;
				self.render();
			},
		});
	}

	addButton(kind) {
		if (this.state.buttons.length >= WA.MAX_BUTTONS) {
			frappe.show_alert({ message: __('You can add up to {0} buttons.', [WA.MAX_BUTTONS]), indicator: 'orange' });
			return;
		}
		this.state.buttons.push({ kind, label: '', url: '', phone_number: '', example: '' });
	}

	/* ---- partial refreshes ---- */

	onBodyInput(val) {
		this.state.body = val;
		this.updateBodyCount(val);
		this.softRefreshSamples();
		this.softRefreshPreview();
		this.softRefreshCompliance();
	}

	softRefreshSamples() {
		const vars = this.detectVars(this.state.body);
		const $existingCard = this.$body.find('.wtb-sample-rows').closest('.wtb-card');
		if (vars.length) {
			const newCardHtml = this.renderSamples();
			if ($existingCard.length) {
				$existingCard.replaceWith(newCardHtml);
			} else {
				const $bodyBlock = this.$body.find('[data-block="body"]');
				if ($bodyBlock.length) $bodyBlock.after(newCardHtml);
			}
			const self = this;
			this.$body.find('[data-sample]').off('input').on('input', function () {
				self.state.samples[String($(this).data('sample'))] = $(this).val();
				self.softRefreshPreview();
			});
			this.$body.find('[data-field-map]').off('change').on('change', function () {
				const n = String($(this).data('field-map'));
				const fieldname = $(this).val();
				self.state.fields[n] = fieldname;
				if (fieldname) self.fillSampleFromField(n, fieldname);
			});
			this.$body.find('[data-fill-all]').off('click').on('click', () => self.fillAllSamplesFromFields());
		} else if ($existingCard.length) {
			$existingCard.remove();
		}
	}

	updateBodyCount(val) {
		const el = this.$body.find('[data-block="body"] .wtb-meta-row');
		el.find('span:first').text(`${this.detectVars(val).length} ${__('variables detected')}`);
		const c = el.find('span:last');
		c.text(`${val.length} / ${WA.BODY_MAX}`).toggleClass('is-over', val.length > WA.BODY_MAX);
	}

	updateHeaderCount(val) {
		const c = this.$body.find('[data-block="header"] .wtb-meta-row span:last');
		c.text(`${val.length} / ${WA.HEADER_MAX}`).toggleClass('is-over', val.length > WA.HEADER_MAX);
	}

	softRefreshPreview() {
		const $old = this.$body.find('.wtb-preview');
		if ($old.length) $old.replaceWith(this.renderPreview());
	}

	softRefreshCompliance() {
		const $c = this.$body.find('.wtb-compliance');
		if ($c.length) $c.replaceWith(this.renderCompliance());
	}

	/* ---- textarea helpers ---- */

	bodyEl() { return this.$body.find('textarea[data-field="body"]')[0]; }

	wrapSelection(mark) {
		const el = this.bodyEl();
		if (!el) return;
		const { selectionStart: a, selectionEnd: b, value } = el;
		const sel = value.slice(a, b) || __('text');
		const next = value.slice(0, a) + mark + sel + mark + value.slice(b);
		el.value = next;
		el.focus();
		el.setSelectionRange(a + mark.length, a + mark.length + sel.length);
		this.onBodyInput(next);
	}

	insertAtCursor(text) {
		const el = this.bodyEl();
		if (!el) { this.state.body += text; return; }
		const { selectionStart: a, selectionEnd: b, value } = el;
		const next = value.slice(0, a) + text + value.slice(b);
		el.value = next;
		this.state.body = next;
		el.focus();
		el.setSelectionRange(a + text.length, a + text.length);
	}

	/* ---- drag and drop ---- */

	enableDnD() {
		if (this.state.locked) return; // view-only: no reordering
		if (typeof Sortable === 'undefined') return;
		const rows = this.$body.find('.wtb-btn-rows')[0];
		if (rows) {
			Sortable.create(rows, {
				handle: '.wtb-grip', draggable: '.wtb-btn-row', animation: 150,
				onEnd: (evt) => {
					if (evt.oldIndex === evt.newIndex) return;
					const moved = this.state.buttons.splice(evt.oldIndex, 1)[0];
					this.state.buttons.splice(evt.newIndex, 0, moved);
					this.render();
				},
			});
		}
	}

	/* ---------------- save ---------------- */

	buildPayload() {
		const s = this.state;
		const vars = this.detectVars(s.body);
		return {
			template_name: (s.template_name || '').trim(),
			category: s.category,
			language: s.language,
			whatsapp_account: s.whatsapp_account,
			for_doctype: s.for_doctype || '',
			body: s.body,
			footer: s.components.footer ? s.footer : '',
			header: s.components.header ? { type: s.header.type, text: s.header.text, sample: s.header.sample } : {},
			sample_values: vars.map((n) => this.sampleFor(n)),
			field_names: vars.map((n) => this.fieldFor(n)),
			buttons: s.components.buttons
				? s.buttons.filter((b) => (b.label || '').trim()).map((b) => ({
					kind: b.kind, label: b.label, url: b.url, phone_number: b.phone_number,
					example: b.kind === 'url' && b.url && b.url.includes('{{')
						? (b.example || null)
						: null,
				}))
				: [],
		};
	}

	validate(submit) {
		const s = this.state;
		if (!(s.template_name || '').trim()) { frappe.show_alert({ message: __('Template Name is required'), indicator: 'red' }); return false; }
		if (!/^[a-z0-9_]+$/.test(s.template_name.trim())) { frappe.show_alert({ message: __('Template Name may only contain lowercase letters, numbers and underscores'), indicator: 'red' }); return false; }
		if (!s.body.trim()) { frappe.show_alert({ message: __('Body text is required'), indicator: 'red' }); return false; }
		if (s.body.length > WA.BODY_MAX) { frappe.show_alert({ message: __('Body exceeds {0} characters', [WA.BODY_MAX]), indicator: 'red' }); return false; }

		const vars = this.detectVars(s.body);
		if (!this.isContiguousVars(vars)) {
			frappe.show_alert({ message: __('Variables must be numbered consecutively starting at {{1}} (e.g. {{1}}, {{2}})'), indicator: 'red' });
			return false;
		}

		if (s.for_doctype && vars.length > 0) {
			const mappedCount = vars.filter((n) => this.fieldFor(n)).length;
			if (mappedCount > 0 && mappedCount < vars.length) {
				frappe.show_alert({ message: __('Either map all variables to fields or leave all unmapped'), indicator: 'red' });
				return false;
			}
		}

		if (s.components.buttons) {
			for (const b of s.buttons) {
				if (b.kind === 'url' && b.url && b.url.includes('{{') && submit && !(b.example || '').trim()) {
					frappe.show_alert({ message: __('Add an example URL for the website button'), indicator: 'red' });
					return false;
				}
			}
		}

		if (s.components.header && s.header.type !== 'TEXT' && !s.header.sample && submit) {
			frappe.show_alert({ message: __('Upload a {0} for the header, or remove it', [s.header.type.toLowerCase()]), indicator: 'red' }); return false;
		}
		if (submit) {
			const missing = vars.filter((n) => this.sampleFor(n) === '');
			if (missing.length) { frappe.show_alert({ message: __('Add sample values for: {0}', [missing.map((n) => '{{' + n + '}}').join(', ')]), indicator: 'red' }); return false; }
			if (!s.whatsapp_account) { frappe.show_alert({ message: __('Select a WhatsApp Account to submit'), indicator: 'red' }); return false; }
		}
		return true;
	}

	async save(submit) {
		if (this.saving) return;
		if (!this.validate(submit)) return;
		this.saving = true;
		const $btn = this.$body.find(submit ? '[data-act="submit"]' : '[data-act="save-draft"]');
		$btn.prop('disabled', true);
		frappe.dom.freeze(submit ? __('Submitting to Meta…') : __('Saving draft…'));
		try {
			const r = await frappe.call({
				method: `${WA.API}.save_template`,
				args: { payload: this.buildPayload(), submit: submit ? 1 : 0, name: this.editName || null },
			});
			const res = r.message;
			frappe.show_alert(
				{
					message: submit
						? __('Template on Meta — status: {0}', [res.status || 'Pending'])
						: __('Draft saved'),
					indicator: 'green',
				},
				5
			);
			// Stay on the builder: switch into edit mode for this template and
			// refresh state (status, meta id) from the server.
			await this.openTemplate(res.name, { quiet: true });
		} catch (e) {
			console.error(e);
		} finally {
			frappe.dom.unfreeze();
			$btn.prop('disabled', false);
			this.saving = false;
		}
	}

	/* ---------------- lifecycle: open / new / delete / sync ---------------- */

	/** Load a template into the builder and enter edit mode (no page reload). */
	async openTemplate(name, opts = {}) {
		try {
			const loaded = await frappe.call(`${WA.API}.load_template`, { name }).then((r) => r.message);
			this.editName = name;
			this.hydrate(loaded);
			if (this.state.for_doctype) await this.loadDoctypeFields(this.state.for_doctype);
			window.history.replaceState(null, '', `/app/template-builder?name=${encodeURIComponent(name)}`);
			this.render();
			if (!opts.quiet) frappe.show_alert({ message: __('Opened {0}', [name]), indicator: 'blue' }, 3);
		} catch (e) {
			frappe.show_alert({ message: __('Could not load template {0}', [name]), indicator: 'red' });
		}
	}

	openTemplateDialog() {
		const d = new frappe.ui.Dialog({
			title: __('Open Template'),
			fields: [{
				fieldtype: 'Link', options: 'WhatsApp Templates',
				fieldname: 'template', label: __('Template'), reqd: 1,
			}],
			primary_action_label: __('Open'),
			primary_action: (v) => { d.hide(); this.openTemplate(v.template); },
		});
		d.show();
	}

	/** Start a fresh template, keeping account/language/category for convenience. */
	newTemplate() {
		const keep = {
			whatsapp_account: this.state.whatsapp_account,
			language: this.state.language,
			category: this.state.category,
		};
		this.editName = null;
		this.state = Object.assign(this.blankState(), keep);
		this.doctypeFields = [];
		window.history.replaceState(null, '', '/app/template-builder');
		this.render();
	}

	/** Copy an approved (locked) template into a fresh, editable draft. */
	duplicateTemplate() {
		// A Flow / Multi-Product Message / Catalog button has no builder
		// equivalent, so the copy would come out silently missing it. Refuse
		// rather than hand back a template that looks complete but is not.
		const unsupported = (this.state.buttons || []).filter((b) => b.unsupported);
		if (unsupported.length) {
			frappe.msgprint({
				title: __('Cannot duplicate here'),
				indicator: 'orange',
				message: __('This template uses button types the builder cannot edit ({0}). Duplicate it from the WhatsApp Templates form so the buttons are preserved.',
					[unsupported.map((b) => b.kind).join(', ')]),
			});
			return;
		}
		const copy = JSON.parse(JSON.stringify(this.state));
		copy.status = null;
		copy.has_meta_id = false;
		copy.locked = false;
		copy.template_name = `${copy.template_name}_copy`.slice(0, 512);
		this.editName = null;
		this.state = copy;
		window.history.replaceState(null, '', '/app/template-builder');
		this.render();
		frappe.show_alert({ message: __('Duplicated as a new draft — rename and submit'), indicator: 'blue' }, 5);
	}

	deleteTemplate() {
		if (!this.editName) return;
		frappe.confirm(
			__('Delete template {0}? If it exists on Meta it will be deleted there too.', [`<b>${frappe.utils.escape_html(this.editName)}</b>`]),
			() => {
				frappe.call('frappe.client.delete', { doctype: 'WhatsApp Templates', name: this.editName })
					.then(() => {
						frappe.show_alert({ message: __('Template deleted'), indicator: 'green' }, 4);
						this.newTemplate();
					});
			}
		);
	}

	/** Pull latest status for this template from Meta. */
	async syncStatus() {
		if (!this.editName) return;
		frappe.dom.freeze(__('Syncing status from Meta…'));
		try {
			const res = await frappe.call({
				method: `${WA.API}.sync_template`,
				args: { name: this.editName },
			}).then((r) => r.message || {});
			await this.openTemplate(this.editName, { quiet: true });
			// Distinguish a real refresh from a no-op; a server-side failure
			// throws and is handled below rather than reported as success.
			if (res.synced) {
				frappe.show_alert({ message: __('Status refreshed: {0}', [res.status]), indicator: 'green' }, 3);
			} else {
				frappe.show_alert({ message: res.reason || __('Nothing to sync'), indicator: 'orange' }, 5);
			}
		} catch (e) {
			console.error(e);
			frappe.show_alert({ message: __('Could not refresh status from Meta'), indicator: 'red' }, 5);
		} finally {
			frappe.dom.unfreeze();
		}
	}
}
