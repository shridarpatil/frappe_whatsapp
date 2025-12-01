import frappe
from frappe.utils.password import set_encrypted_password, get_decrypted_password


def execute():
    # Read old settings using raw SQL since the fields may have been removed from the schema
    # but the data might still exist in the singles table
    old_settings = get_old_settings_from_singles()

    if not old_settings:
        return

    phone_id = old_settings.get("phone_id")

    if not phone_id:
        return

    if frappe.db.exists("WhatsApp Account", {"phone_id": phone_id}):
        return

    # Get token from __Auth table (Password fields are stored there, not in tabSingles)
    token = get_decrypted_password("WhatsApp Settings", "WhatsApp Settings", "token", raise_exception=False)

    if not token:
        return

    enabled = old_settings.get("enabled")

    account = frappe.get_doc({
        "doctype": "WhatsApp Account",
        "account_name": "Default WhatsApp Account",
        "phone_id": phone_id,
        "business_id": old_settings.get("business_id"),
        "app_id": old_settings.get("app_id"),
        "url": old_settings.get("url"),
        "version": old_settings.get("version"),
        "webhook_verify_token": old_settings.get("webhook_verify_token"),
        "is_default_incoming": 1,
        "is_default_outgoing": 1,
        "status": "Active" if enabled in (1, "1") else "Inactive"
    })
    account.insert(ignore_permissions=True)

    # Set the password using Frappe's password utility to store in __Auth table
    set_encrypted_password("WhatsApp Account", account.name, token, "token")

    update_whatsapp_settings(account.name)
    update_whatsapp_templates(account.name)

    frappe.db.commit()


def update_whatsapp_settings(account_name: str):
    """Update WhatsApp Settings with the new default account."""
    settings = frappe.get_single("WhatsApp Settings")
    settings.default_incoming_account = account_name
    settings.default_outgoing_account = account_name
    settings.save(ignore_permissions=True)


def get_old_settings_from_singles():
    """Read old WhatsApp Settings fields directly from the singles table.

    This bypasses the ORM since the field definitions may have been removed
    from the doctype schema, but the data might still exist in the database.
    Note: token is not included here as it's stored in __Auth table.
    """
    fields_to_migrate = [
        "phone_id",
        "business_id",
        "app_id",
        "url",
        "version",
        "webhook_verify_token",
        "enabled",
    ]

    result = frappe.db.sql(
        """
        SELECT field, value
        FROM `tabSingles`
        WHERE doctype = 'WhatsApp Settings'
        AND field IN %s
        """,
        (fields_to_migrate,),
        as_dict=True
    )

    if not result:
        return None

    return {row["field"]: row["value"] for row in result}


def update_whatsapp_templates(account_name: str):
    templates = frappe.get_all(
        "WhatsApp Templates",
        filters={"whatsapp_account": ""},
        fields=["name"]
    )
    for template in templates:
        frappe.db.set_value("WhatsApp Templates", template["name"], "whatsapp_account", account_name)
