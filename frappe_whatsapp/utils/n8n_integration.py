import frappe
import json
from frappe_whatsapp.utils.webhook import webhook

@frappe.whitelist(allow_guest=True)
def receive_n8n_message():
	"""
	Receives a simplified or flattened JSON payload from n8n (or other sources),
	wraps it in the standard Meta Webhook structure, and passes it to the
	existing webhook handler.
	"""
	# 1. Get the raw JSON payload
	# frappe.request is available in whitelisted methods
	try:
		data = frappe.request.get_json()
	except Exception:
		# Fallback if content-type is not application/json
		data = frappe.local.form_dict

	if not data:
		return "No JSON data received"

	# 2. Handle List (n8n might send an array of items) vs Dict
	if isinstance(data, list):
		if not data:
			return "Empty List"
		payload = data[0]
	else:
		payload = data

	# 3. Construct the standard Meta Webhook structure
	# Defensive check: if it's already in 'entry' format, just use it.
	if "entry" in payload:
		frappe.local.form_dict = frappe._dict(payload)
		return webhook()

	# Wrap the payload into the structure expected by frappe_whatsapp.utils.webhook.post
	# Expects: entry[0].changes[0].value.messages
	meta_wrapper = {
		"object": "whatsapp_business_account",
		"entry": [
			{
				"id": "n8n_forwarded",
				"changes": [
					{
						"value": payload,
						"field": "messages"
					}
				]
			}
		]
	}

	# 4. Inject into frappe.local.form_dict so webhook.post() can read it
	# We merge with existing form_dict to preserve other params if any, but overwrite conflict
	if frappe.local.form_dict:
		frappe.local.form_dict.update(meta_wrapper)
	else:
		frappe.local.form_dict = frappe._dict(meta_wrapper)
	
	# 5. Call the original webhook logic
	# context: webhook() calls post() because we are in a POST request
	return webhook()


@frappe.whitelist(allow_guest=True)
def log_outgoing_message():
    """
    Endpoint for n8n to log messages it HAS SENT to the user.
    
    For text messages, expects:
    {
        "to": "91999...",
        "message": "content",
        "message_id": "wamid...",
        "content_type": "text"
    }
    
    For template messages, expects:
    {
        "to": "91999...",
        "template_name": "bhm_shop_start_v2",
        "template_lang": "en",
        "template_params": ["John", "order123"],
        "message_id": "wamid...",
        "content_type": "template"
    }
    """
    import re
    from frappe_whatsapp.utils import get_whatsapp_account

    data = frappe.local.form_dict
    # Try to parse JSON if sent as raw body
    try:
        if not data and frappe.request and frappe.request.get_json():
            data = frappe.request.get_json()
    except Exception:
        pass

    to_number = data.get("to")
    if not to_number:
        return {"status": "skipped", "reason": "Missing 'to'"}

    # Resolve WhatsApp Account
    phone_id = data.get("phone_id")
    account = get_whatsapp_account(phone_id)
    if not account:
        account = get_whatsapp_account()
    if not account:
        return {"status": "error", "reason": "No WhatsApp Account found"}

    # Determine if this is a template or text message
    template_name = data.get("template_name")
    template_lang = data.get("template_lang", "en")
    
    doc_fields = {
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "to": to_number,
        "message_id": data.get("message_id"),
        "whatsapp_account": account.name,
        "status": "Sent",
    }

    if template_name:
        # --- Template message ---
        # Look up the template by actual_name (lowercase slug)
        template_doc = None
        if frappe.db.exists("WhatsApp Templates", {"actual_name": template_name}):
            template_doc = frappe.get_doc("WhatsApp Templates", {"actual_name": template_name})
        elif frappe.db.exists("WhatsApp Templates", {"template_name": template_name}):
            template_doc = frappe.get_doc("WhatsApp Templates", {"template_name": template_name})

        if template_doc:
            # Render the template body by replacing {{1}}, {{2}}, etc.
            rendered_body = template_doc.template or ""
            template_params = data.get("template_params") or []
            
            # Ensure template_params is a list
            if isinstance(template_params, str):
                try:
                    template_params = json.loads(template_params)
                except (json.JSONDecodeError, ValueError):
                    template_params = [template_params]

            for i, param_value in enumerate(template_params, start=1):
                rendered_body = rendered_body.replace(f"{{{{{i}}}}}", str(param_value))

            # Build full message with header + body + footer
            parts = []
            if template_doc.header:
                header_text = template_doc.header
                header_params = data.get("header_params") or []
                if isinstance(header_params, str):
                    try:
                        header_params = json.loads(header_params)
                    except (json.JSONDecodeError, ValueError):
                        header_params = [header_params]
                for i, param_value in enumerate(header_params, start=1):
                    header_text = header_text.replace(f"{{{{{i}}}}}", str(param_value))
                parts.append(f"*{header_text}*")  # Bold header
            
            parts.append(rendered_body)
            
            if template_doc.footer:
                parts.append(f"_{template_doc.footer}_")  # Italic footer

            rendered_message = "\n\n".join(parts)

            doc_fields.update({
                "message": rendered_message,
                "content_type": "text",
                "message_type": "Template",
                "use_template": 1,
                "template": template_doc.name,
                "template_parameters": json.dumps(template_params) if template_params else None,
            })
        else:
            # Template not found — log with raw info
            doc_fields.update({
                "message": f"[Template: {template_name} ({template_lang})]",
                "content_type": "text",
                "message_type": "Template",
            })
    else:
        # --- Plain text message ---
        message_content = data.get("message")
        if not message_content:
            return {"status": "skipped", "reason": "Missing 'message'"}
        
        doc_fields.update({
            "message": message_content,
            "content_type": data.get("content_type", "text"),
        })

    # Use db_insert to bypass before_insert hook (which would try to re-send via API)
    doc = frappe.get_doc(doc_fields)
    doc.db_insert()
    frappe.db.commit()

    return {"status": "success", "name": doc.name}

