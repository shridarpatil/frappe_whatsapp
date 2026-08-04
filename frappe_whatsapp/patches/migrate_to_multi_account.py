import frappe
from frappe.utils.password import get_decrypted_password, set_encrypted_password

LEGACY_FIELDS = (
    "phone_id",
    "business_id",
    "app_id",
    "url",
    "version",
    "webhook_verify_token",
    "enabled",
)


def execute():
    log = frappe.logger("frappe_whatsapp.migrate_to_multi_account")

    old_settings = get_old_settings_from_singles()
    if not old_settings:
        log.info("no legacy WhatsApp Settings rows in tabSingles; nothing to migrate")
        return

    phone_id = old_settings.get("phone_id")
    if not phone_id:
        log.info("legacy settings have no phone_id; nothing to migrate")
        return

    existing_account = frappe.db.exists("WhatsApp Account", {"phone_id": phone_id})
    if existing_account:
        account_name = existing_account
        log.info(f"WhatsApp Account already exists for phone_id={phone_id}; reusing {account_name}")
    else:
        # Token lives in __Auth, not tabSingles
        token = get_decrypted_password(
            "WhatsApp Settings", "WhatsApp Settings", "token", raise_exception=False
        )
        if not token:
            log.warning("no token in __Auth for WhatsApp Settings; cannot create account")
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
            "status": "Active" if enabled in (1, "1") else "Inactive",
        })
        account.insert(ignore_permissions=True)
        set_encrypted_password("WhatsApp Account", account.name, token, "token")
        account_name = account.name
        log.info(f"created WhatsApp Account {account_name}")

    # Always run these so installs with a pre-existing account still get
    # WhatsApp Settings defaults and orphan templates fixed up.
    update_whatsapp_settings(account_name)
    update_whatsapp_templates(account_name)


def update_whatsapp_settings(account_name: str):
    settings = frappe.get_single("WhatsApp Settings")
    settings.default_incoming_account = account_name
    settings.default_outgoing_account = account_name
    settings.save(ignore_permissions=True)


def get_old_settings_from_singles():
    """Read legacy WhatsApp Settings fields directly from tabSingles.

    Bypasses the ORM because the field definitions were removed from the
    doctype schema in the multi-account refactor; the data may still
    survive in the singles table. Token is stored in __Auth, not here.
    """
    result = frappe.db.sql(
        """
        SELECT field, value
        FROM `tabSingles`
        WHERE doctype = 'WhatsApp Settings'
        AND field IN %s
        """,
        (LEGACY_FIELDS,),
        as_dict=True,
    )
    if not result:
        return None
    return {row["field"]: row["value"] for row in result}


def update_whatsapp_templates(account_name: str):
    # Pre-multi-account template rows have whatsapp_account = NULL (column
    # added by schema migration with no default), not "". The ORM filter
    # {"whatsapp_account": ""} misses NULLs in MariaDB, so use raw SQL.
    frappe.db.sql(
        """
        UPDATE `tabWhatsApp Templates`
        SET whatsapp_account = %s
        WHERE whatsapp_account IS NULL OR whatsapp_account = ''
        """,
        (account_name,),
    )
