# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt

import json
import frappe
import requests
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request
from io import BytesIO

def generate_pdf(doc_type, doc_name):
    pdf_content = frappe.get_print(doc_type, doc_name, as_pdf=True)
    return BytesIO(pdf_content)

def upload_pdf_to_whatsapp(pdf_file, filename):
    settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    access_token = settings.get_password("token")
    phone_number_id = settings.phone_id
    url = f"{settings.url}/{settings.version}/{phone_number_id}/media"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    files = {
        "file": (filename, pdf_file, "application/pdf"),
        "type": (None, "application/pdf"),
        "messaging_product": (None, "whatsapp")
    }

    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()["id"]

def send_document_message(phone_number, media_id, filename):
    settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    access_token = settings.get_password("token")
    phone_number_id = settings.phone_id
    url = f"{settings.url}/{settings.version}/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

class WhatsAppMessage(Document):
    """Send WhatsApp messages."""

    def before_insert(self):
        """Send message before inserting the document."""
        if self.type == "Outgoing" and self.message_type != "Template":
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + "/" + self.attach
            else:
                link = self.attach

            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(self.to),
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

            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
                frappe.throw(f"Failed to send message: {str(e)}")
        elif self.type == "Outgoing" and self.message_type == "Template" and not self.message_id:
            self.send_template()

    def send_template(self):
        """Send template message with optional PDF attachment."""
        template = frappe.get_doc("WhatsApp Templates", self.template)
        data = {
            "messaging_product": "whatsapp",
            "to": self.format_number(self.to),
            "type": "template",
            "template": {
                "name": template.actual_name or template.template_name,
                "language": {"code": template.language_code},
                "components": [],
            },
        }

        # Prepare body parameters
        if template.sample_values:
            field_names = (
                template.field_names.split(",")
                if template.field_names
                else template.sample_values.split(",")
            )
            parameters = []
            template_parameters = []

            if self.flags.get("custom_ref_doc"):
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

        # Handle header for IMAGE or DOCUMENT
        if template.header_type and template.sample:
            if template.header_type == "IMAGE":
                url = (
                    template.sample
                    if template.sample.startswith("http")
                    else f"{frappe.utils.get_url()}{template.sample}"
                )
                data["template"]["components"].append(
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {
                                    "link": url
                                }
                            }
                        ],
                    }
                )
            elif template.header_type == "DOCUMENT":
                # Generate PDF
                pdf_content = frappe.get_print(
                    self.reference_doctype, self.reference_name, as_pdf=True
                )
                pdf_file = BytesIO(pdf_content)
                filename = f"{self.reference_name}.pdf"

                # Upload PDF to WhatsApp
                settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
                access_token = settings.get_password("token")
                phone_number_id = settings.phone_id

                media_id = upload_pdf_to_whatsapp(pdf_file, filename)

                # Attach document to the header
                data["template"]["components"].append(
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "document",
                                "document": {
                                    "id": media_id,
                                    "filename": filename,
                                },
                            }
                        ],
                    }
                )
            elif template.header_type == "TEXT":
                data["template"]["components"].append(
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": template.sample
                            }
                        ]
                    }
                )

        self.notify(data)

    def notify(self, data):
        """Send the prepared message data to WhatsApp API."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        token = settings.get_password("token")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers,
                data=json.dumps(data),
            )
            self.message_id = response["messages"][0]["id"]
        except Exception as e:
            res = frappe.flags.integration_request.json().get("error", {})
            error_message = res.get("message", str(e))
            frappe.get_doc(
                {
                    "doctype": "WhatsApp Notification Log",
                    "template": "Text Message",
                    "meta_data": frappe.flags.integration_request.json(),
                }
            ).insert(ignore_permissions=True)

            frappe.throw(msg=error_message, title=res.get("error_user_title", "Error"))

    def format_number(self, number):
        """Format the phone number by removing leading '+' if present."""
        return number[1:] if number.startswith("+") else number


def on_doctype_update():
    """Add index on reference_doctype and reference_name fields."""
    frappe.db.add_index("WhatsApp Message", ["reference_doctype", "reference_name"])

@frappe.whitelist()
def send_template(to, reference_doctype, reference_name, template):
    """Create and send a WhatsApp message using a template."""
    try:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": to,
            "type": "Outgoing",
            "message_type": "Template",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "template": template
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success", "message_id": doc.message_id}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Send WhatsApp Template Failed")
        return {"status": "error", "message": str(e)}
