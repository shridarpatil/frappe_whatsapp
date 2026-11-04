"""Backfill WhatsApp Message.message for template sends that stored structured params
(template_parameters / body_param) but left the display body empty.

Template sends go through WhatsAppMessage.send_template(), which built the Meta payload
but never set `message`, so the conversation panel (which renders `message`) showed empty
bubbles for ~half of all template messages. The forward fix now renders the body into
`message` at send time; this patch repairs the historical rows.

Idempotent and display-only: it only fills rows whose `message` is currently empty, and
never overwrites an existing body.
"""

import json

import frappe

BATCH_COMMIT = 2000


def execute():
    templates = {
        t.name: (t.template or "")
        for t in frappe.get_all("WhatsApp Templates", fields=["name", "template"])
    }

    rows = frappe.db.sql(
        """
        SELECT name, template, template_parameters, body_param
        FROM `tabWhatsApp Message`
        WHERE message_type = 'Template'
          AND (message IS NULL OR message = '')
          AND template IS NOT NULL AND template != ''
        """,
        as_dict=True,
    )

    updated = 0
    for i, row in enumerate(rows, 1):
        body = templates.get(row.template)
        if not body:
            continue

        rendered = body
        for idx, value in enumerate(_ordered_params(row.template_parameters, row.body_param), start=1):
            rendered = rendered.replace("{{%d}}" % idx, "" if value is None else str(value))
        rendered = rendered.strip()
        if not rendered:
            continue

        # Display-only fill; don't bump `modified` on a large historical backfill.
        frappe.db.set_value(
            "WhatsApp Message", row.name, "message", rendered, update_modified=False
        )
        updated += 1
        if i % BATCH_COMMIT == 0:
            frappe.db.commit()

    frappe.db.commit()
    frappe.logger().info(
        f"backfill_template_message_body: filled {updated} of {len(rows)} empty template messages"
    )


def _ordered_params(template_parameters, body_param):
    """Ordered param values: prefer the stored ordered list, else body_param's
    numeric-keyed dict ({"1": .., "2": ..}) in key order."""
    if template_parameters:
        try:
            value = json.loads(template_parameters)
            if isinstance(value, list):
                return value
        except (ValueError, TypeError):
            pass
    if body_param:
        try:
            value = json.loads(body_param)
            if isinstance(value, dict):
                keys = sorted((k for k in value if str(k).isdigit()), key=int)
                return [value[k] for k in keys]
        except (ValueError, TypeError):
            pass
    return []
