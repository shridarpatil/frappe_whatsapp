"""Server endpoints for the visual WhatsApp Template Builder page.

The builder is a thin UI over the existing ``WhatsApp Templates`` DocType: on
save it constructs (or updates) a ``WhatsApp Templates`` document plus its
``WhatsApp Button`` child rows. All Meta round-trips (create/update/delete,
media upload, language-code derivation) are handled by the DocType controller
(``whatsapp_templates.py``) — this module never talks to Meta directly.
"""

import json

import frappe
from frappe import _

from frappe_whatsapp.utils import get_whatsapp_account

# Category options come from the WhatsApp Templates DocType schema.
CATEGORY_OPTIONS = ["UTILITY", "MARKETING", "AUTHENTICATION", "TRANSACTIONAL", "OTP"]

# Header formats the DocType controller can push to Meta today. VIDEO/LOCATION
# are intentionally excluded — the controller only handles TEXT/IMAGE/DOCUMENT.
HEADER_TYPES = ["TEXT", "IMAGE", "DOCUMENT"]

# Palette button types the builder can produce, mapped to the WhatsApp Button
# child DocType's `button_type` options that the controller's outbound payload
# builder handles (Quick Reply / Visit Website / Call Phone).
BUTTON_KIND_MAP = {
	"quick_reply": "Quick Reply",
	"url": "Visit Website",
	"phone": "Call Phone",
}
# Reverse map, for loading an existing template back into the builder.
BUTTON_TYPE_TO_KIND = {v: k for k, v in BUTTON_KIND_MAP.items()}


@frappe.whitelist()
def get_boot():
	"""Return option lists the builder UI needs to render its selects."""
	languages = frappe.get_all(
		"Language",
		fields=["name", "language_name"],
		filters={"enabled": 1},
		order_by="language_name asc",
	)

	accounts = frappe.get_all(
		"WhatsApp Account",
		fields=["name", "is_default_outgoing"],
		filters={"status": "Active"},
		order_by="is_default_outgoing desc, name asc",
	)

	default_account = get_whatsapp_account(account_type="outgoing")

	return {
		"categories": CATEGORY_OPTIONS,
		"header_types": HEADER_TYPES,
		"languages": languages,
		"accounts": accounts,
		"default_account": default_account.name if default_account else None,
		"has_account": bool(accounts),
	}


@frappe.whitelist()
def get_doctype_fields(doctype):
	"""Return selectable field names for the "For DocType" variable mapping.

	Only data-bearing fields are useful as template variables, so layout and
	no-value field types are filtered out.
	"""
	if not doctype:
		return []
	skip = {
		"Section Break", "Column Break", "Tab Break", "HTML", "Table",
		"Table MultiSelect", "Button", "Image", "Fold", "Heading",
	}
	meta = frappe.get_meta(doctype)
	fields = [
		{"value": df.fieldname, "label": f"{df.label} ({df.fieldname})" if df.label else df.fieldname}
		for df in meta.fields
		if df.fieldtype not in skip and df.fieldname
	]
	# Common always-present fields worth exposing.
	for extra in ("name", "owner", "creation"):
		fields.insert(0, {"value": extra, "label": extra}) if extra == "name" else fields.append({"value": extra, "label": extra})
	return fields


@frappe.whitelist()
def get_sample_record(doctype, fieldnames=None):
	"""Return formatted sample values from the latest record of `doctype`.

	Used by the builder to auto-fill variable sample values from real data
	once a variable is mapped to a field. Reads the most recently modified
	record the user is permitted to see and formats each requested field the
	same way it is rendered at send time (``get_formatted``).

	Returns ``{"record": <name or None>, "values": {fieldname: formatted}}``.
	"""
	if not doctype:
		return {"record": None, "values": {}}

	# Respect the user's read permission on the source doctype.
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You are not permitted to read {0}").format(doctype))

	names = frappe.get_list(doctype, fields=["name"], order_by="modified desc", limit=1)
	if not names:
		return {"record": None, "values": {}}

	doc = frappe.get_doc(doctype, names[0]["name"])

	# `fieldnames` may arrive as a real list, a JSON-array string (how the JS
	# client's array arg is form-encoded), or a plain comma string.
	requested = fieldnames
	if isinstance(requested, str):
		requested = requested.strip()
		if requested.startswith("["):
			try:
				requested = json.loads(requested)
			except (ValueError, TypeError):
				requested = requested.split(",")
		else:
			requested = requested.split(",")
	requested = [f.strip() for f in (requested or []) if f and f.strip()]

	values = {}
	for fieldname in requested:
		if fieldname == "name":
			values[fieldname] = doc.name
			continue
		try:
			values[fieldname] = doc.get_formatted(fieldname) or ""
		except Exception:
			values[fieldname] = frappe.utils.cstr(doc.get(fieldname) or "")

	return {"record": doc.name, "values": values}


@frappe.whitelist()
def load_template(name):
	"""Load an existing WhatsApp Template into builder state for editing."""
	doc = frappe.get_doc("WhatsApp Templates", name)

	sample_values = doc.sample_values.split(",") if doc.sample_values else []
	field_names = doc.field_names.split(",") if doc.field_names else []

	buttons = []
	for b in doc.buttons:
		kind = BUTTON_TYPE_TO_KIND.get(b.button_type)
		if not kind:
			continue
		buttons.append({
			"kind": kind,
			"label": b.button_label,
			"url": b.website_url,
			"phone_number": b.phone_number,
			"example": b.example_url,
		})

	return {
		"name": doc.name,
		"template_name": doc.template_name,
		"category": doc.category,
		"language": doc.language,
		"whatsapp_account": doc.whatsapp_account,
		"body": doc.template,
		"footer": doc.footer or "",
		"header": {
			"type": doc.header_type or "TEXT",
			"text": doc.header or "",
			"sample": doc.sample or "",
		},
		"for_doctype": doc.for_doctype,
		"sample_values": [v.strip() for v in sample_values],
		"field_names": [v.strip() for v in field_names],
		"buttons": buttons,
		"status": doc.status,
		"has_meta_id": bool(doc.id),
	}


def _coerce(payload):
	if isinstance(payload, str):
		return json.loads(payload)
	return payload or {}


def _apply_payload(doc, data):
	"""Copy builder state onto a WhatsApp Templates doc (new or existing)."""
	doc.template_name = (data.get("template_name") or "").strip()
	doc.template = (data.get("body") or "").strip()
	doc.category = (data.get("category") or "").strip()
	doc.language = (data.get("language") or "").strip()
	doc.footer = (data.get("footer") or "").strip() or None
	doc.for_doctype = (data.get("for_doctype") or "").strip() or None

	if data.get("whatsapp_account"):
		doc.whatsapp_account = data["whatsapp_account"]

	# Header: TEXT sets header text; IMAGE/DOCUMENT set the sample file URL that
	# the controller uploads to Meta on save.
	header = data.get("header") or {}
	header_type = (header.get("type") or "").upper()
	doc.header_type = None
	doc.header = None
	doc.sample = None
	if header_type == "TEXT" and (header.get("text") or "").strip():
		doc.header_type = "TEXT"
		doc.header = header["text"].strip()
	elif header_type in ("IMAGE", "DOCUMENT") and (header.get("sample") or "").strip():
		doc.header_type = header_type
		doc.sample = header["sample"].strip()

	# Sample values (Meta review) + field names (runtime data binding), both
	# comma-separated and ordered by {{1}}, {{2}}, ...
	sample_values = data.get("sample_values") or []
	if isinstance(sample_values, str):
		sample_values = sample_values.split(",")
	doc.sample_values = ",".join(str(v).strip() for v in sample_values) if sample_values else None

	field_names = data.get("field_names") or []
	if isinstance(field_names, str):
		field_names = field_names.split(",")
	# Only persist field_names if at least one is set (otherwise leave blank so
	# send-time falls back to sample_values, matching existing behaviour).
	field_names = [str(v).strip() for v in field_names]
	doc.field_names = ",".join(field_names) if any(field_names) else None

	# Buttons — rebuild the child table from scratch.
	doc.set("buttons", [])
	for btn in data.get("buttons") or []:
		button_type = BUTTON_KIND_MAP.get(btn.get("kind"))
		if not button_type:
			continue
		row = {"button_type": button_type, "button_label": (btn.get("label") or "").strip()}
		if button_type == "Visit Website":
			url = (btn.get("url") or "").strip()
			row["website_url"] = url
			row["url_type"] = "Dynamic" if "{{" in url else "Static"
			if btn.get("example"):
				row["example_url"] = btn["example"]
		elif button_type == "Call Phone":
			row["phone_number"] = (btn.get("phone_number") or "").strip()
		doc.append("buttons", row)


def _validate(data):
	if not (data.get("template_name") or "").strip():
		frappe.throw(_("Template Name is required"))
	if not (data.get("body") or "").strip():
		frappe.throw(_("Body text is required"))
	category = (data.get("category") or "").strip()
	if category not in CATEGORY_OPTIONS:
		frappe.throw(_("Invalid category: {0}").format(category))
	if not (data.get("language") or "").strip():
		frappe.throw(_("Language is required"))


@frappe.whitelist()
def save_template(payload, submit=0, name=None):
	"""Create or update a WhatsApp Templates document from builder state.

	Args:
		payload: dict (or JSON string) of the builder's state.
		submit: when truthy, the DocType controller pushes to Meta on save;
			when falsy (Save Draft) a local row is persisted without a Meta call.
		name: when provided, update that existing template instead of creating.

	Returns the document name so the UI can deep-link to the form.
	"""
	data = _coerce(payload)
	submit = frappe.utils.cint(submit)
	_validate(data)

	if submit and not data.get("whatsapp_account") and not get_whatsapp_account(account_type="outgoing"):
		frappe.throw(_("Select a WhatsApp Account to submit the template to Meta"))

	is_update = bool(name)
	doc = frappe.get_doc("WhatsApp Templates", name) if is_update else frappe.new_doc("WhatsApp Templates")
	_apply_payload(doc, data)

	# A draft skips the Meta round-trip and the account requirement.
	if not submit:
		doc.flags.skip_meta_submit = True

	if is_update:
		# update_template() only pushes when the row already has a Meta id;
		# a local draft edit therefore persists without any Meta call.
		first_submit = submit and not doc.id
		doc.save()
		if first_submit:
			# Draft being submitted for the first time: the row already exists
			# locally, so after_insert (the Meta create path) must run manually.
			# save() above already uploaded any media header sample.
			doc.after_insert()
			doc.reload()
	else:
		doc.insert()

	return {
		"name": doc.name,
		"status": doc.status,
		"submitted": bool(submit),
		"updated": is_update,
	}
