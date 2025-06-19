# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe import _, throw
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request

from frappe_whatsapp.utils import get_whatsapp_account, format_number

class WhatsAppMessage(Document):
    def validate(self):
        self.set_whatsapp_account()

    def on_update(self):
        self.update_profile_name()

    def update_profile_name(self):
        from_number = format_number(self.get("from"))

        if (
            self.has_value_changed("profile_name")
            and self.profile_name
            and from_number
            and frappe.db.exists("WhatsApp Profiles", {"number": from_number})
        ):
            profile_id = frappe.get_value("WhatsApp Profiles", {"number": from_number}, "name")
            frappe.db.set_value("WhatsApp Profiles", profile_id, "profile_name", self.profile_name)

    def create_whatsapp_profile(self):
        number = format_number(self.get("from") or self.to)
        if not frappe.db.exists("WhatsApp Profiles", {"number": number}):
            frappe.get_doc({
                "doctype": "WhatsApp Profiles",
                "profile_name": self.profile_name,
                "number": number,
                "whatsapp_account": self.whatsapp_account
            }).insert(ignore_permissions=True)

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
        if self.type == "Outgoing" and self.message_type != "Template":
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
                data["text"] = {"link": link}

            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
                frappe.throw(f"Failed to send message {str(e)}")
        elif self.type == "Outgoing" and self.message_type == "Template" and not self.message_id:
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

        if template.sample_values:
            field_names = template.field_names.split(",") if template.field_names else template.sample_values.split(",")
            parameters = []
            template_parameters = []

            if self.flags.custom_ref_doc:
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

            data["template"]["components"].append(
                {
                    "type": "body",
                    "parameters": parameters,
                }
            )

        if template.header_type and template.sample:
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

        self.notify(data)
        self.create_whatsapp_profile()

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
            res = frappe.flags.integration_request.json()["error"]
            error_message = res.get("Error", res.get("message"))
            frappe.get_doc(
                {
                    "doctype": "WhatsApp Notification Log",
                    "template": "Text Message",
                    "meta_data": frappe.flags.integration_request.json(),
                }
            ).insert(ignore_permissions=True)

            frappe.throw(msg=error_message, title=res.get("error_user_title", "Error"))

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
