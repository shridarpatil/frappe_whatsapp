# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe import _, throw
from frappe.utils import cint, add_to_date, now_datetime
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request
import urllib.parse

from frappe_whatsapp.utils import get_whatsapp_account, format_number

class WhatsAppMessage(Document):
    def validate(self):
        self.set_whatsapp_account()

    def on_update(self):
        self.update_profile_name()

    def update_profile_name(self):
        number = self.get("from")
        if not number:
            return
        from_number = format_number(number)

        if (
            self.has_value_changed("profile_name")
            and self.profile_name
            and from_number
            and frappe.db.exists("WhatsApp Profiles", {"number": from_number})
        ):
            profile_id = frappe.get_value("WhatsApp Profiles", {"number": from_number}, "name")
            frappe.db.set_value("WhatsApp Profiles", profile_id, "profile_name", self.profile_name)

    def create_whatsapp_profile(self):
        # Opt-out switch in WhatsApp Settings. An absent single value casts to 0, which
        # coincides with the default (create), so existing/fresh sites keep current
        # behaviour; only an explicit 1 ("Disable WhatsApp Profile Creation") skips it.
        if cint(frappe.db.get_single_value("WhatsApp Settings", "disable_whatsapp_profiles")):
            return

        raw_number = self.get("from") or self.to
        if not raw_number:
            return
        number = format_number(raw_number)
        if frappe.db.exists("WhatsApp Profiles", {"number": number}):
            return

        # `number` is unique: two concurrent messages from the same new number can both
        # pass the exists() check above, so the loser of the race hits the unique index.
        # Contain that failure in a savepoint so it can never abort the parent WhatsApp
        # Message insert.
        savepoint = "create_whatsapp_profile"
        try:
            frappe.db.savepoint(savepoint)
            frappe.get_doc({
                "doctype": "WhatsApp Profiles",
                "profile_name": self.profile_name,
                "number": number,
                "whatsapp_account": self.whatsapp_account
            }).insert(ignore_permissions=True)
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback(save_point=savepoint)

    def set_whatsapp_account(self):
        """Set whatsapp account to default if missing"""
        if not self.whatsapp_account:
            account_type = 'outgoing' if self.type == 'Outgoing' else 'incoming'
            default_whatsapp_account = get_whatsapp_account(account_type=account_type)
            if not default_whatsapp_account:
                throw(_("Please set a default outgoing WhatsApp Account or Select available WhatsApp Account"))
            else:
                self.whatsapp_account = default_whatsapp_account.name

    """Send whats app messages."""
    def before_insert(self):
        """Send message."""
        self.set_whatsapp_account()
        # Route to template path when a template is selected,
        # since message_type is read_only and cannot be set from the UI.
        if self.template:
            self.message_type = "Template"
        self.send_outgoing()
        self.create_whatsapp_profile()

    def send_outgoing(self):
        """Dispatch an Outgoing message to Meta.

        Called from `before_insert` for first-time sends and from bulk
        retry for re-sending Failed messages. No-op for non-Outgoing docs.
        On non-template sends, raises and sets status to Failed on error;
        on template sends, `send_template` -> `notify` raises on error.
        """
        if self.type != "Outgoing":
            return

        if self.message_type != "Template":
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + "/" + self.attach
            else:
                link = self.attach

            data = {
                "messaging_product": "whatsapp",
                "to": format_number(self.to),
                "type": self.content_type,
            }
            if self.is_reply and self.reply_to_message_id:
                data["context"] = {"message_id": self.reply_to_message_id}
            if self.content_type in ["document", "image", "video"]:
                data[self.content_type.lower()] = {
                    "link": link,
                    "caption": self.message,
                }
            elif self.content_type == "reaction":
                data["reaction"] = {
                    "message_id": self.reply_to_message_id,
                    "emoji": self.message,
                }
            elif self.content_type == "text":
                data["text"] = {"preview_url": True, "body": self.message}

            elif self.content_type == "audio":
                data["audio"] = {"link": link}

            elif self.content_type == "interactive":
                # Interactive message (buttons or list)
                data["type"] = "interactive"
                buttons_data = json.loads(self.buttons) if isinstance(self.buttons, str) else self.buttons

                if isinstance(buttons_data, list) and len(buttons_data) > 3:
                    # Use list message for more than 3 options (max 10)
                    data["interactive"] = {
                        "type": "list",
                        "body": {"text": self.message},
                        "action": {
                            "button": "Select Option",
                            "sections": [{
                                "title": "Options",
                                "rows": [
                                    {"id": btn["id"], "title": btn["title"], "description": btn.get("description", "")}
                                    for btn in buttons_data[:10]
                                ]
                            }]
                        }
                    }
                else:
                    # Use button message for 3 or fewer options
                    data["interactive"] = {
                        "type": "button",
                        "body": {"text": self.message},
                        "action": {
                            "buttons": [
                                {
                                    "type": "reply",
                                    "reply": {"id": btn["id"], "title": btn["title"]}
                                }
                                for btn in buttons_data[:3]
                            ]
                        }
                    }

            elif self.content_type == "flow":
                # WhatsApp Flow message
                if not self.flow:
                    frappe.throw(_("WhatsApp Flow is required for flow content type"))

                flow_doc = frappe.get_doc("WhatsApp Flow", self.flow)

                if not flow_doc.flow_id:
                    frappe.throw(_("Flow must be created on WhatsApp before sending"))

                # Determine flow mode - draft flows can be tested with mode: "draft"
                flow_mode = None
                if flow_doc.status != "Published":
                    flow_mode = "draft"
                    frappe.msgprint(_("Sending flow in draft mode (for testing only)"), indicator="orange")

                # Get first screen if not specified
                flow_screen = self.flow_screen
                if not flow_screen and flow_doc.screens:
                    flow_screen = flow_doc.screens[0].screen_id

                data["type"] = "interactive"
                data["interactive"] = {
                    "type": "flow",
                    "body": {"text": self.message or "Please fill out the form"},
                    "action": {
                        "name": "flow",
                        "parameters": {
                            "flow_message_version": "3",
                            "flow_id": flow_doc.flow_id,
                            "flow_cta": self.flow_cta or flow_doc.flow_cta or "Open",
                            "flow_action": "navigate",
                            "flow_action_payload": {
                                "screen": flow_screen
                            }
                        }
                    }
                }

                # Add draft mode for testing unpublished flows
                if flow_mode:
                    data["interactive"]["action"]["parameters"]["mode"] = flow_mode

                # Add flow token - generate one if not provided (required by WhatsApp)
                flow_token = self.flow_token or frappe.generate_hash(length=16)
                data["interactive"]["action"]["parameters"]["flow_token"] = flow_token

            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
                frappe.throw(f"Failed to send message {str(e)}")
        elif not self.message_id:
            self.send_template()

    def send_template(self):
        """Send template."""
        template = frappe.get_doc("WhatsApp Templates", self.template)
        data = {
            "messaging_product": "whatsapp",
            "to": format_number(self.to),
            "type": "template",
            "template": {
                "name": template.actual_name or template.template_name,
                "language": {"code": template.language_code},
                "components": [],
            },
        }

        parameters = []
        template_parameters = []
        if template.sample_values:
            field_names = template.field_names.split(",") if template.field_names else template.sample_values.split(",")

            if self.body_param is not None:
                params = list(json.loads(self.body_param).values())
                for param in params:
                    parameters.append({"type": "text", "text": param})
                    template_parameters.append(param)
            elif self.flags.custom_ref_doc:
                custom_values = self.flags.custom_ref_doc
                for field_name in field_names:
                    value = custom_values.get(field_name.strip())
                    parameters.append({"type": "text", "text": value})
                    template_parameters.append(value)                    

            else:
                ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
                for field_name in field_names:
                    value = ref_doc.get_formatted(field_name.strip())
                    parameters.append({"type": "text", "text": value})
                    template_parameters.append(value)

            self.template_parameters = json.dumps(template_parameters)

        # Populate `message` with the rendered template body so the conversation panel
        # (and anything else that reads `message`) shows real text instead of an empty
        # bubble. Only when the caller hasn't already supplied a display body — template
        # sends via `send_template` otherwise leave `message` blank.
        if not self.message:
            self.message = self._render_template_body(template, template_parameters)

        # Always add the body component, even if parameters list is empty
        data["template"]["components"].append({
            "type": "body",
            "parameters": parameters,
        })

        if template.header_type:
            if self.attach:
                if self.attach.startswith("http"):
                    url = f'{self.attach}'
                else:
                    url = f'{frappe.utils.get_url()}{self.attach}'
                if template.header_type == 'IMAGE':
                    data['template']['components'].append({
                        "type": "header",
                        "parameters": [{
                            "type": "image",
                            "image": {
                                "link": url
                            }
                        }]
                    })

                elif template.header_type == 'DOCUMENT':
                    data['template']['components'].append({
                        "type": "header",
                        "parameters": [{
                            "type": "document",
                            "document": {
                                "link": url,
                                "filename": "document.pdf"  # should be configurable
                            }
                        }]
                    })

            elif template.sample:
                if template.header_type == 'IMAGE':
                    if template.sample.startswith("http"):
                        url = f'{template.sample}'
                    else:
                        url = f'{frappe.utils.get_url()}{template.sample}'
                    data['template']['components'].append({
                        "type": "header",
                        "parameters": [{
                            "type": "image",
                            "image": {
                                "link": url
                            }
                        }]
                    })

        if template.need_dynamic_button_url_parameter:
            button_field_names = template.field_name_for_button_parameter.split(",")
            button_parameters = []
            template_button_parameters = []
            if self.flags.custom_ref_doc:
                custom_values = self.flags.custom_ref_doc
                for field_name in button_field_names:
                    value = custom_values.get(field_name.strip())
                    encoded_value = urllib.parse.quote(value) if value else value
                    button_parameters.append({"type": "text", "text": encoded_value})
                    template_button_parameters.append(value)
            else:
                ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
                for field_name in button_field_names:
                    value = ref_doc.get_formatted(field_name.strip())
                    encoded_value = urllib.parse.quote(value) if value else value
                    button_parameters.append({"type": "text", "text": encoded_value})
                    template_button_parameters.append(value)
            self.template_button_parameters = json.dumps(template_button_parameters)
            data["template"]["components"].append({
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": button_parameters
            })

        # We check this before standard buttons because MPM is an interactive action
        has_mpm = False
        if self.product_catalog_json:
            try:
                catalog_data = json.loads(self.product_catalog_json)
                data['template']['components'].append({
                    "type": "button",
                    "sub_type": "mpm",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "action",
                            "action": catalog_data
                        }
                    ]
                })
                has_mpm = True
            except Exception as e:
                frappe.log_error(f"Failed to parse Product Catalog JSON: {str(e)}", "WhatsApp MPM Error")

        if template.buttons:
            # Only buttons with *runtime* parameters go into components.
            # Static Call Phone and static Visit Website buttons are applied
            # by Meta from the approved template — sending them here yields
            # "sub_type must be one of {...}" errors since Meta no longer
            # accepts `phone_number`. See issue #188.
            button_parameters = []
            for idx, btn in enumerate(template.buttons):
                # Shift index if MPM was added at index 0
                current_idx = str(idx + 1) if has_mpm else str(idx)

                if btn.button_type == "Quick Reply":
                    button_parameters.append({
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": current_idx,
                        "parameters": [{"type": "payload", "payload": btn.button_label}]
                    })
                elif btn.button_type == "Visit Website" and btn.url_type == "Dynamic":
                    # ptstdm dynamic-URL model takes precedence: when
                    # need_dynamic_button_url_parameter is set, the URL button
                    # param is built above from field_name_for_button_parameter.
                    # Skip here to avoid an empty param (Meta 400) and a
                    # duplicate index-0 button component.
                    if template.need_dynamic_button_url_parameter:
                        continue
                    ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
                    url = ref_doc.get_formatted(btn.website_url)
                    button_parameters.append({
                        "type": "button",
                        "sub_type": "url",
                        "index": current_idx,
                        "parameters": [{"type": "text", "text": url}]
                    })

            if button_parameters:
                data['template']['components'].extend(button_parameters)

        self.notify(data)

    def _render_template_body(self, template, template_parameters):
        """Build a human-readable body from a WhatsApp template + its ordered parameters,
        substituting {{1}}, {{2}}, ... placeholders. Display-only (chat panel / list view);
        the actual send uses the structured `components` payload, not this string."""
        body = template.template or ""
        for index, value in enumerate(template_parameters, start=1):
            body = body.replace("{{%d}}" % index, "" if value is None else str(value))
        return body.strip()

    def notify(self, data):
        """Notify."""
        whatsapp_account = frappe.get_doc(
            "WhatsApp Account",
            self.whatsapp_account,
        )
        token = whatsapp_account.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        }
        try:
            response = make_post_request(
                f"{whatsapp_account.url}/{whatsapp_account.version}/{whatsapp_account.phone_id}/messages",
                headers=headers,
                data=json.dumps(data),
            )
            self.message_id = response["messages"][0]["id"]

        except Exception as e:
            res = frappe.flags.integration_request.json().get("error", {})
            error_message = res.get("Error", res.get("message"))
            frappe.get_doc(
                {
                    "doctype": "WhatsApp Notification Log",
                    "template": "Text Message",
                    "meta_data": frappe.flags.integration_request.json(),
                }
            ).insert(ignore_permissions=True)

            frappe.throw(msg=error_message, title=res.get("error_user_title", "Error"))

    def format_number(self, number):
        """Format number."""
        if number.startswith("+"):
            number = number[1 : len(number)]

        return number

    @frappe.whitelist()
    def send_read_receipt(self):
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": self.message_id
        }

        settings = frappe.get_doc(
            "WhatsApp Account",
            self.whatsapp_account,
        )

        token = settings.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        }
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers,
                data=json.dumps(data),
            )

            if response.get("success"):
                self.status = "marked as read"
                self.save()
                return response.get("success")

        except Exception as e:
            res = frappe.flags.integration_request.json().get("error", {})
            error_message = res.get("Error", res.get("message"))
            frappe.log_error("WhatsApp API Error", f"{error_message}\n{res}")

    @staticmethod
    def clear_old_logs(days=90):
        """Delete WhatsApp Messages older than `days`.

        Registered with Frappe's Log Settings via the `default_log_clearing_doctypes`
        hook, so the daily log-cleanup job trims old incoming/outgoing messages
        (default 90 days, editable under Log Settings). Keyed on `creation` so it
        means "message is older than N days" regardless of later status webhooks
        bumping `modified`. Deleted in batches because this table grows into the
        hundreds of thousands of rows and a single unbounded DELETE would hold a
        long table lock and bloat the transaction.
        """
        cutoff = add_to_date(now_datetime(), days=-cint(days))
        while True:
            names = frappe.get_all(
                "WhatsApp Message",
                filters={"creation": ["<", cutoff]},
                pluck="name",
                order_by="creation asc",
                limit=10000,
            )
            if not names:
                break
            frappe.db.delete("WhatsApp Message", {"name": ["in", names]})
            # nosemgrep: frappe-manual-commit -- batched cleanup runs inside the scheduled
            # log-clean-up job (outside request scope); commit each batch so table locks and
            # the undo log don't grow unbounded while deleting large backlogs.
            frappe.db.commit()


def on_doctype_update():
    frappe.db.add_index("WhatsApp Message", ["reference_doctype", "reference_name"])


@frappe.whitelist()
def send_template(to, reference_doctype, reference_name, template):
    try:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": to,
            "type": "Outgoing",
            "message_type": "Template",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "content_type": "text",
            "template": template
        })

        doc.save()
    except Exception as e:
        raise e
