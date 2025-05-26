import frappe

def field_exists(doctype, fieldname):
	meta = frappe.get_meta(doctype)
	return any(df.fieldname == fieldname for df in meta.fields)

def execute():
	if not field_exists("WhatsApp Settings", "phone_id") or not field_exists("WhatsApp Settings", "token"):
		return

	settings = frappe.get_single("WhatsApp Settings")

	existing = frappe.get_all("WhatsApp Account", filters={"phone_id": settings.phone_id})
	if existing:
		return

	account = frappe.get_doc({
		"doctype": "WhatsApp Account",
		"account_name": "Default WhatsApp Account",
		"phone_id": settings.phone_id,
		"business_id": settings.business_id,
		"app_id": settings.app_id,
		"token": settings.get_password("token"),
		"url": settings.url,
		"version": settings.version,
		"webhook_verify_token": settings.webhook_verify_token,
		"token": settings.token,
		"is_default_incoming": 1,
		"is_default_outgoing": 1,
		"status": "Active" if settings.enabled == 1 else "Inactive"
	})
	account.insert(ignore_permissions=True)
	settings.save()
	update_whatsapp_templates(account.name)
	frappe.db.commit()

def update_whatsapp_templates(account):
	whatsapp_templates = frappe.get_all(
		'WhatsApp Templates',
		filters={'whatsapp_account': ''},
		fields=['name']
	)
	for template in whatsapp_templates:
		frappe.db.set_value('WhatsApp Templates', template['name'], 'whatsapp_account', account)
