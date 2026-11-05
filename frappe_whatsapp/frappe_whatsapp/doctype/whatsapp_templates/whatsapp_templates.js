// Copyright (c) 2022, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on('WhatsApp Templates', {
	// Mirror the server-side checks so the user gets immediate feedback before the
	// save round-trip. The server (validate) stays authoritative.
	validate: function (frm) {
		const example = "Ravi,10 AM,04 Oct 2026 07:24 PM";

		// SRO-2026-10-00227: a media header needs a sample file.
		if (["IMAGE", "DOCUMENT"].includes(frm.doc.header_type) && !frm.doc.sample) {
			frappe.throw(__("Header Type {0} needs a sample file for Meta review. Attach one in Sample.", [frm.doc.header_type]));
		}

		// Open Point 1: BODY sample values must match the {{n}} placeholders.
		const body = frm.doc.template || "";
		const nums = (body.match(/\{\{\s*\d+\s*\}\}/g) || []).map(m => parseInt(m.replace(/\D/g, ""), 10));
		const distinct = Array.from(new Set(nums)).sort((a, b) => a - b);
		const n = distinct.length;

		for (let i = 0; i < n; i++) {
			if (distinct[i] !== i + 1) {
				// No replace-args: keep the literal {{1}} in the message.
				frappe.throw(__("Template variables must be numbered sequentially starting at {{1}} with no gaps."));
			}
		}

		const raw = frm.doc.sample_values || "";
		if (n === 0) {
			if (raw.trim()) {
				frappe.throw(__("The template body has no variables, so Sample Values must be empty."));
			}
			// Normalise whitespace-only input to empty, matching the server.
			frm.doc.sample_values = "";
			return;
		}
		if (/[\r\n]/.test(raw)) {
			frappe.throw(__("Sample Values must be on a single line. Write one value per variable, separated by commas. Example: ") + example);
		}
		const values = raw.split(",").map(v => v.trim());
		if (!raw.trim() || values.length !== n || values.some(v => v === "")) {
			const got = raw.trim() ? values.length : 0;
			frappe.throw(__("The template has {0} variable(s) but Sample Values has {1}. Write one value per variable on one line, separated by commas (no comma inside a value). Example: {2}", [n, got, example]));
		}
	}
});
