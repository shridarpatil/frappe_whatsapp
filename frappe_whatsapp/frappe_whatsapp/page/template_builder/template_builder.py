"""Server endpoints for the visual WhatsApp Template Builder page.

The builder is a thin UI over the existing ``WhatsApp Templates`` DocType: on
save it constructs (or updates) a ``WhatsApp Templates`` document plus its
``WhatsApp Button`` child rows. All Meta round-trips (create/update/delete,
media upload, language-code derivation) are handled by the DocType controller
(``whatsapp_templates.py``) — this module never talks to Meta directly.
"""

import json
import re

import frappe
from frappe import _
from frappe.integrations.utils import make_request

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

# A template that already exists on Meta (it has a Meta template id) is
# view-only in the builder: Meta does not reliably allow editing submitted
# templates (PENDING cannot be edited at all, APPROVED only within tight
# limits), so pushed templates are frozen here — read, duplicate or delete
# only. The status check is a safety net for rows synced without an id.
LOCKED_STATUSES = {"APPROVED"}


def parse_list(val):
	"""Parse a JSON array string or comma-separated string into a list of strings."""
	if not val:
		return []
	if isinstance(val, list):
		return [str(v) for v in val]
	if isinstance(val, str):
		val = val.strip()
		if not val:
			return []
		if val.startswith("[") and val.endswith("]"):
			try:
				parsed = json.loads(val)
				if isinstance(parsed, list):
					return [str(v) for v in parsed]
			except (ValueError, TypeError):
				pass
		return [v.strip() for v in val.split(",")]
	return []


def serialize_list(lst):
	"""Serialize a list of strings to JSON string if any element contains a comma, else comma-separated string."""
	if not lst:
		return None
	clean = [str(v).strip() for v in lst]
	if not any(clean):
		return None
	if any("," in v for v in clean):
		return json.dumps(clean)
	return ",".join(clean)


def _is_locked(doc):
	has_unsupported_buttons = any(
		(b.button_type or "") not in BUTTON_TYPE_TO_KIND for b in (doc.get("buttons") or [])
	)
	return bool(doc.id) or (doc.status or "").upper() in LOCKED_STATUSES or has_unsupported_buttons


@frappe.whitelist()
def get_boot():
	"""Return option lists the builder UI needs to render its selects."""
	languages = frappe.get_all(
		"Language",
		fields=["name", "language_name"],
		filters={"enabled": 1},
		order_by="language_name asc",
	)

	# get_list (not get_all) so account names stay behind read permission.
	accounts = frappe.get_list(
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
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You are not permitted to read {0}").format(doctype))
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
	fields.insert(0, {"value": "name", "label": "name"})
	fields.extend({"value": extra, "label": extra} for extra in ("owner", "creation"))
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

	meta = frappe.get_meta(doctype)
	if meta.issingle:
		doc = frappe.get_single(doctype)
	else:
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
	doc.check_permission("read")

	sample_values = parse_list(doc.sample_values)
	field_names = parse_list(doc.field_names)

	buttons = []
	for b in doc.buttons:
		kind = BUTTON_TYPE_TO_KIND.get(b.button_type)
		buttons.append({
			"kind": kind or b.button_type,
			"label": b.button_label,
			"url": b.website_url,
			"phone_number": b.phone_number,
			"example": b.example_url,
			"unsupported": not bool(kind),
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
		"sample_values": sample_values,
		"field_names": field_names,
		"buttons": buttons,
		"status": doc.status,
		"has_meta_id": bool(doc.id),
		"locked": _is_locked(doc),
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
	# Derive language_code here, not just in validate(): autoname
	# (format:{template_name}-{language_code}) runs before validate, so a
	# new document would otherwise be named with an empty suffix.
	if doc.language:
		lang_code = frappe.db.get_value("Language", doc.language) or "en"
		doc.language_code = lang_code.replace("-", "_")
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
		if (header.get("sample") or "").strip():
			doc.sample = header["sample"].strip()
	elif header_type in ("IMAGE", "DOCUMENT"):
		doc.header_type = header_type
		if (header.get("sample") or "").strip():
			doc.sample = header["sample"].strip()

	# Sample values (Meta review) + field names (runtime data binding), both
	# serialized cleanly and ordered by {{1}}, {{2}}, ...
	sample_values = parse_list(data.get("sample_values"))
	doc.sample_values = serialize_list(sample_values)

	raw_field_names = parse_list(data.get("field_names"))
	# Only persist field_names if EVERY variable is mapped, matching existing behaviour requirement.
	if raw_field_names and all(f.strip() for f in raw_field_names) and len(raw_field_names) == len(sample_values):
		doc.field_names = serialize_list(raw_field_names)
	else:
		doc.field_names = None

	# Buttons — rebuild the child table from scratch.
	doc.set("buttons", [])
	for btn in data.get("buttons") or []:
		kind = btn.get("kind")
		button_type = BUTTON_KIND_MAP.get(kind)
		if not button_type:
			# Flow / Multi-Product Message / Catalog have no builder equivalent.
			# Silently dropping them would save a template that looks complete
			# but has lost a button (the duplicate-an-approved-template path),
			# so refuse the write and say which type is the problem.
			frappe.throw(
				_("Button type {0} cannot be edited in the Template Builder. "
				  "Edit this template from the WhatsApp Templates form instead.").format(kind or _("(unknown)"))
			)
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
	template_name = (data.get("template_name") or "").strip()
	if not template_name:
		frappe.throw(_("Template Name is required"))
	if not re.fullmatch(r"[a-z0-9_]+", template_name):
		# Meta's naming rule; also mirrored client-side.
		frappe.throw(_("Template Name may only contain lowercase letters, numbers and underscores"))
	body_text = (data.get("body") or "").strip()
	if not body_text:
		frappe.throw(_("Body text is required"))

	# Check contiguous variable numbering starting from {{1}}
	vars_found = [int(m) for m in re.findall(r"\{\{\s*(\d+)\s*\}\}", body_text)]
	if vars_found:
		unique_vars = sorted(list(set(vars_found)))
		expected = list(range(1, len(unique_vars) + 1))
		if unique_vars != expected:
			frappe.throw(_("Variables in body must be numbered consecutively starting at {{1}} (e.g. {{1}}, {{2}})"))

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

	is_update = bool(name)
	doc = frappe.get_doc("WhatsApp Templates", name) if is_update else frappe.new_doc("WhatsApp Templates")

	# A template that already exists on Meta is frozen — refuse any write to it.
	# This is checked first (before the account guard) so the caller always sees
	# the real reason, and before _apply_payload overwrites the doc in memory.
	if is_update and _is_locked(doc):
		frappe.throw(
			_("Template {0} has already been submitted to Meta and can no longer be edited. "
			  "Duplicate it as a new template instead.").format(doc.name)
		)

	if submit and not data.get("whatsapp_account") and not get_whatsapp_account(account_type="outgoing"):
		frappe.throw(_("Select a WhatsApp Account to submit the template to Meta"))

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


@frappe.whitelist()
def sync_template(name):
	"""Refresh Meta status for a single template document.

	Returns ``{"name", "status", "synced", "reason"}``. ``synced`` is False when
	nothing was fetched, with ``reason`` explaining why, so the UI can tell a
	real refresh apart from a no-op instead of always reporting success.
	"""
	if not name:
		return {"name": None, "status": None, "synced": False, "reason": _("No template specified.")}

	doc = frappe.get_doc("WhatsApp Templates", name)
	# This persists the fetched status, so it is a write, not a read.
	doc.check_permission("write")

	if not doc.id:
		return {
			"name": doc.name,
			"status": doc.status,
			"synced": False,
			"reason": _("This template has not been submitted to Meta yet."),
		}
	if not doc.whatsapp_account:
		return {
			"name": doc.name,
			"status": doc.status,
			"synced": False,
			"reason": _("This template has no WhatsApp Account set."),
		}

	account = frappe.get_doc("WhatsApp Account", doc.whatsapp_account)
	headers = {
		"authorization": f"Bearer {account.get_password('token')}",
		"content-type": "application/json",
	}

	try:
		response = make_request(
			"GET",
			f"{account.url}/{account.version}/{doc.id}?fields=status",
			headers=headers,
		)
	except Exception:
		# Surface the failure instead of reporting a successful no-op — an
		# expired token or a template deleted on Meta must not look like "ok".
		frappe.log_error(
			title="WhatsApp Template status sync failed",
			message=frappe.get_traceback(),
		)
		frappe.throw(
			_("Could not fetch the status for {0} from Meta. See the Error Log for details.").format(doc.name)
		)

	status = (response or {}).get("status")
	if not status:
		return {
			"name": doc.name,
			"status": doc.status,
			"synced": False,
			"reason": _("Meta did not return a status for this template."),
		}

	if status != doc.status:
		doc.db_set("status", status, update_modified=False)

	return {"name": doc.name, "status": status, "synced": True, "reason": None}
