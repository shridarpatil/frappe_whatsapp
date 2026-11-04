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
        # A reused account (manual setup, an earlier partial run, or a restore) may never
        # have had the legacy token copied onto it — only the create branch below sets it.
        # A tokenless account can't authenticate to Meta, so outgoing sends fail. Backfill
        # it here, idempotently, without clobbering a token the account already holds.
        backfill_account_token(account_name, log)
    else:
        # Token lives in __Auth, not tabSingles
        token = get_decrypted_password(
            "WhatsApp Settings", "WhatsApp Settings", "token", raise_exception=False
        )
        if not token:
            log.warning("no token in __Auth for WhatsApp Settings; cannot create account")
            return

        enabled = old_settings.get("enabled")
        # webhook_verify_token is a Password field, so its real value is in __Auth;
        # tabSingles only holds the masked "******" placeholder. Read the decrypted
        # value (not old_settings, which came from tabSingles) or the account ends up
        # with a literal "******" that breaks Meta webhook re-verification.
        webhook_verify_token = get_decrypted_password(
            "WhatsApp Settings", "WhatsApp Settings", "webhook_verify_token", raise_exception=False
        )
        account = frappe.get_doc({
            "doctype": "WhatsApp Account",
            "account_name": "Default WhatsApp Account",
            "phone_id": phone_id,
            "business_id": old_settings.get("business_id"),
            "app_id": old_settings.get("app_id"),
            "url": old_settings.get("url"),
            "version": old_settings.get("version"),
            "webhook_verify_token": webhook_verify_token,
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


def backfill_account_token(account_name: str, log):
    """Copy the legacy WhatsApp Settings token onto an existing account that has none.

    The create branch only sets the token on accounts it inserts; an account reused via
    the existing_account branch can end up tokenless, which breaks outgoing sends. This
    fills that gap idempotently and is safe to re-run:
      - never overwrites a token the account already has (decryptable or not), and
      - no-ops when there is no legacy token to copy.
    """
    try:
        if get_decrypted_password("WhatsApp Account", account_name, "token", raise_exception=False):
            return  # account already has a usable token — leave it
    except Exception:
        return  # token row present but undecryptable (e.g. key mismatch) — don't clobber

    try:
        legacy_token = get_decrypted_password(
            "WhatsApp Settings", "WhatsApp Settings", "token", raise_exception=False
        )
    except Exception:
        legacy_token = None

    if not legacy_token:
        log.warning(f"{account_name} has no token and no legacy token to backfill")
        return

    set_encrypted_password("WhatsApp Account", account_name, legacy_token, "token")
    log.info(f"backfilled legacy token onto existing WhatsApp Account {account_name}")


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
