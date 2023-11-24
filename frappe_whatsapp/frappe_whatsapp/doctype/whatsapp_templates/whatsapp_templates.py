"""Create whatsapp template."""
# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request, make_request
from frappe.desk.form.utils import get_pdf_link


class WhatsAppTemplates(Document):
    """Create whatsapp template."""

    def after_insert(self):
        """Set template code."""
        self.template_name = self.template_name.lower().replace(' ', '_')
        self.language_code = frappe.db.get_value(
            "Language", self.language
        ).replace('-', '_')

        self.get_settings()
        data = {
            "name": self.template_name,
            "language": self.language_code,
            "category": self.category,
            "components": []
        }

        body = {
            "type": "BODY",
            "text": self.template,
        }
        if self.sample_values:
            body.update({
                "example": {
                    "body_text": [self.sample_values.split(',')]
                }
            })

        data['components'].append(body)
        if self.header_type:
            data['components'].append(self.get_header())

        # add footer
        if self.footer:
            data['components'].append({
                "type": "FOOTER",
                "text": self.footer
            })

        try:
            response = make_post_request(
                f"{self._url}/{self._version}/{self._business_id}/message_templates",
                headers=self._headers, data=json.dumps(data)
            )
            self.id = response['id']
            self.status = response['status']
            # frappe.db.set_value("WhatsApp Templates", self.name, "id", response['id'])
        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('error_user_msg', res.get("message"))
            frappe.throw(
                msg=error_message,
                title=res.get("error_user_title", "Error"),
            )

    def on_update(self):
        """Update template to meta."""
        self.get_settings()
        data = {
            "components": []
        }

        body = {
            "type": "BODY",
            "text": self.template,
        }
        if self.sample_values:
            body.update({
                "example": {
                    "body_text": [self.sample_values.split(',')]
                }
            })
        data['components'].append(body)
        if self.header_type:
            data['components'].append(self.get_header())
        if self.footer:
            data['components'].append({
                "type": "FOOTER",
                "text": self.footer
            })
        try:
            # post template to meta for update
            response = make_post_request(
                f"{self._url}/{self._version}/{self.id}",
                headers=self._headers, data=json.dumps(data)
            )
        except Exception as e:
            raise e
            res = frappe.flags.integration_request.json()['error']
            frappe.throw(
                msg=res.get('error_user_msg', res.get("message")),
                title=res.get("error_user_title", "Error"),
            )


    def get_settings(self):
        """Get whatsapp settings."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        self._token = settings.get_password("token")
        self._url = settings.url
        self._version = settings.version
        self._business_id = settings.business_id

        self._headers = {
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json"
        }

    def on_trash(self):
        self.get_settings()
        url = f'{self._url}/{self._version}/{self._business_id}/message_templates?name={self.name}'
        try:
            make_request("DELETE", url, headers=self._headers)
        except Exception:
            res = frappe.flags.integration_request.json()['error']
            if res.get("error_user_title") == "Message Template Not Found":
                frappe.msgprint("Deleted locally", res.get("error_user_title", "Error"), alert=True)
            else:
                frappe.throw(
                    msg=res.get("error_user_msg"),
                    title=res.get("error_user_title", "Error"),
                )

    def get_header(self):
        """Get header format."""
        header = {
            "type": "header",
            "format": self.header_type
        }
        if self.header_type == "TEXT":
            header['text'] = self.header

        else:
            if not self.sample:
                key = frappe.get_doc(self.doctype, self.name).get_document_share_key()
                link = get_pdf_link(self.doctype, self.name)
                self.sample = f'{frappe.utils.get_url()}{link}&key={key}'
            header.update({"example": {
                "header_handle": [self.sample]
            }})

        return header


@frappe.whitelist()
def fetch():
    """Fetch templates from meta."""

    # get credentials
    settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    token = settings.get_password("token")
    url = settings.url
    version = settings.version
    business_id = settings.business_id

    headers = {
        "authorization": f"Bearer {token}",
        "content-type": "application/json"
    }

    try:
        response = make_request(
            "GET",
            f"{url}/{version}/{business_id}/message_templates",
            headers=headers,
        )

        for template in response['data']:
            # set flag to insert or update
            flags = 1
            if frappe.db.exists("WhatsApp Templates", template['name']):
                doc = frappe.get_doc("WhatsApp Templates", template['name'])
            else:
                flags = 0
                doc = frappe.new_doc("WhatsApp Templates")
                doc.template_name = template['name']

            doc.status = template['status']
            doc.language_code = template['language']
            doc.category = template['category']
            doc.id = template['id']

            # update components
            for component in template['components']:

                # update header
                if component['type'] == "HEADER":
                    doc.header_type = component['format']

                    # if format is text update sample text
                    if component['format'] == 'TEXT':
                        doc.header = component['text']
                # Update footer text
                elif component['type'] == 'FOOTER':
                    doc.footer = component['text']

                # update template text
                elif component['type'] == 'BODY':
                    doc.template = component['text']
                    if component.get('example'):
                        doc.sample_values = ','.join(component['example']['body_text'][0])

            # if document exists update else insert
            # used db_update and db_insert to ignore hooks
            if flags:
                doc.db_update()
            else:
                doc.db_insert()
            frappe.db.commit()

    except Exception as e:
        res = frappe.flags.integration_request.json()['error']
        error_message = res.get('error_user_msg', res.get("message"))
        frappe.throw(
            msg=error_message,
            title=res.get("error_user_title", "Error"),
        )

    return "Successfully fetched templates from meta"