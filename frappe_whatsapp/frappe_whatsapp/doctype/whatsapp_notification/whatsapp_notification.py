"""Notification."""

import json
import frappe

from frappe import _dict, _
from frappe.model.document import Document
from frappe.utils.safe_exec import get_safe_globals, safe_exec
from frappe.integrations.utils import make_post_request
from frappe.desk.form.utils import get_pdf_link
from frappe.utils import add_to_date, nowdate, datetime


class WhatsAppNotification(Document):
    """Notification."""

    def validate(self):
        """Validate."""
        if self.notification_type == "DocType Event":
            fields = frappe.get_doc("DocType", self.reference_doctype).fields
            fields += frappe.get_all(
                "Custom Field",
                filters={"dt": self.reference_doctype},
                fields=["fieldname"]
            )
            if not any(field.fieldname == self.field_name for field in fields): # noqa
                frappe.throw(_("Field name {0} does not exists").format(self.field_name))
        if self.custom_attachment:
            if not self.attach and not self.attach_from_field:
                frappe.throw(_("Either {0} a file or add a {1} to send attachemt").format(
                    frappe.bold(_("Attach")),
                    frappe.bold(_("Attach from field")),
                ))

        if self.set_property_after_alert:
            meta = frappe.get_meta(self.reference_doctype)
            if not meta.get_field(self.set_property_after_alert):
                frappe.throw(_("Field {0} not found on DocType {1}").format(
                    self.set_property_after_alert,
                    self.reference_doctype,
                ))


    def send_scheduled_message(self) -> dict:
        """Specific to API endpoint Server Scripts."""
        safe_exec(
            self.condition, get_safe_globals(), dict(doc=self)
        )

        template = frappe.db.get_value(
            "WhatsApp Templates", self.template,
            fieldname='*'
        )

        if template and template.language_code:
            if self.get("_contact_list"):
                # send simple template without a doc to get field data.
                self.send_simple_template(template)
            elif self.get("_data_list"):
                # allow send a dynamic template using schedule event config
                # _doc_list shoud be [{"name": "xxx", "phone_no": "123"}]
                for data in self._data_list:
                    doc = frappe.get_doc(self.reference_doctype, data.get("name"))

                    self.send_template_message(doc, data.get("phone_no"), template, True)
        # return _globals.frappe.flags


    def send_simple_template(self, template):
        """ send simple template without a doc to get field data """
        for contact in self._contact_list:
            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(contact),
                "type": "template",
                "template": {
                    "name": template.actual_name,
                    "language": {
                        "code": template.language_code
                    },
                    "components": []
                }
            }
            self.content_type = template.get("header_type", "text").lower()
            self.notify(data)


    def send_template_message(self, doc: Document, phone_no=None, default_template=None, ignore_condition=False):
        """Specific to Document Event triggered Server Scripts."""
        if self.disabled:
            return

        doc_data = doc.as_dict()
        if self.condition and not ignore_condition:
            # check if condition satisfies
            if not frappe.safe_eval(
                self.condition, get_safe_globals(), dict(doc=doc_data)
            ):
                return

        template = default_template or frappe.get_doc("WhatsApp Templates", self.template)

        if template:
            if self.field_name:
                phone_number = phone_no or doc_data[self.field_name]
            else:
                phone_number = phone_no

            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(phone_number),
                "type": "template",
                "template": {
                    "name": template.actual_name,
                    "language": {
                        "code": template.language_code
                    },
                    "components": []
                }
            }

            # Pass parameter values
            if self.fields:
                parameters = []
                for field in self.fields:
                    if isinstance(doc, Document):
                        # get field with prettier value.
                        value = doc.get_formatted(field.field_name)
                    else: 
                        value = doc_data[field.field_name]
                        if isinstance(doc_data[field.field_name], (datetime.date, datetime.datetime)):
                            value = str(doc_data[field.field_name])

                    parameters.append({
                        "type": "text",
                        "text": value
                    })

                data['template']["components"] = [{
                    "type": "body",
                    "parameters": parameters
                }]

            if self.attach_document_print:
                # frappe.db.begin()
                key = doc.get_document_share_key()  # noqa
                frappe.db.commit()
                print_format = "Standard"
                doctype = frappe.get_doc("DocType", doc_data['doctype'])
                if doctype.custom:
                    if doctype.default_print_format:
                        print_format = doctype.default_print_format
                else:
                    default_print_format = frappe.db.get_value(
                        "Property Setter",
                        filters={
                            "doc_type": doc_data['doctype'],
                            "property": "default_print_format"
                        },
                        fieldname="value"
                    )
                    print_format = default_print_format if default_print_format else print_format
                link = get_pdf_link(
                    doc_data['doctype'],
                    doc_data['name'],
                    print_format=print_format
                )

                filename = f'{doc_data["name"]}.pdf'
                url = f'{frappe.utils.get_url()}{link}&key={key}'

            elif self.custom_attachment:
                filename = self.file_name

                if self.attach_from_field:
                    file_url = doc_data[self.attach_from_field]
                    if not file_url.startswith("http"):
                        # get share key so that private files can be sent
                        key = doc.get_document_share_key()
                        file_url = f'{frappe.utils.get_url()}{file_url}&key={key}'
                else:
                    file_url = self.attach

                if file_url.startswith("http"):
                    url = f'{file_url}'
                else:
                    url = f'{frappe.utils.get_url()}{file_url}'

            if template.header_type == 'DOCUMENT':
                data['template']['components'].append({
                    "type": "header",
                    "parameters": [{
                        "type": "document",
                        "document": {
                            "link": url,
                            "filename": filename
                        }
                    }]
                })
            elif template.header_type == 'IMAGE':
                data['template']['components'].append({
                    "type": "header",
                    "parameters": [{
                        "type": "image",
                        "image": {
                            "link": url
                        }
                    }]
                })
            self.content_type = template.header_type.lower()

            if template.buttons:
                button_fields = self.button_fields.split(",") if self.button_fields else []
                for idx, btn in enumerate(template.buttons):
                    if btn.button_type == "Visit Website" and btn.url_type == "Dynamic":
                        if button_fields:
                            data['template']['components'].append({
                                "type": "button",
                                "sub_type": "url",
                                "index": str(idx),
                                "parameters": [
                                    {"type": "text", "text": doc.get(button_fields.pop(0))}
                                ]
                            })

            self.notify(data, doc_data)

    def notify(self, data, doc_data=None):
        """Notify."""
        settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
        token = settings.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }
        try:
            success = False
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers, data=json.dumps(data)
            )

            if not self.get("content_type"):
                self.content_type = 'text'

            parameters = None
            if data["template"]["components"]:
                parameters = [param["text"] for param in data["template"]["components"][0]["parameters"]]
                parameters = frappe.json.dumps(parameters, default=str)

            new_doc = {
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "message": str(data['template']),
                "to": data['to'],
                "message_type": "Template",
                "message_id": response['messages'][0]['id'],
                "content_type": self.content_type,
                "use_template": 1,
                "template": self.template,
                "template_parameters": parameters
            }

            if doc_data:
                new_doc.update({
                    "reference_doctype": doc_data.doctype,
                    "reference_name": doc_data.name,
                })

            frappe.get_doc(new_doc).save(ignore_permissions=True)

            if doc_data and self.set_property_after_alert and self.property_value:
                if doc_data.doctype and doc_data.name:
                    fieldname = self.set_property_after_alert
                    value = self.property_value
                    meta = frappe.get_meta(doc_data.get("doctype"))
                    df = meta.get_field(fieldname)
                    if df:
                        if df.fieldtype in frappe.model.numeric_fieldtypes:
                            value = frappe.utils.cint(value)

                        frappe.db.set_value(doc_data.get("doctype"), doc_data.get("name"), fieldname, value)

            frappe.msgprint("WhatsApp Message Triggered", indicator="green", alert=True)
            success = True

        except Exception as e:
            error_message = str(e)
            if frappe.flags.integration_request:
                response = frappe.flags.integration_request.json()['error']
                error_message = response.get('Error', response.get("message"))

            frappe.msgprint(
                f"Failed to trigger whatsapp message: {error_message}",
                indicator="red",
                alert=True
            )
        finally:
            if not success:
                meta = {"error": error_message}
            else:
                meta = frappe.flags.integration_request.json()
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": self.template,
                "meta_data": meta
            }).insert(ignore_permissions=True)


    def on_trash(self):
        """On delete remove from schedule."""
        frappe.cache().delete_value("whatsapp_notification_map")


    def format_number(self, number):
        """Format number."""
        if (number.startswith("+")):
            number = number[1:len(number)]

        return number

    def get_documents_for_today(self):
        """get list of documents that will be triggered today"""
        docs = []

        diff_days = self.days_in_advance
        if self.doctype_event == "Days After":
            diff_days = -diff_days

        reference_date = add_to_date(nowdate(), days=diff_days)
        reference_date_start = reference_date + " 00:00:00.000000"
        reference_date_end = reference_date + " 23:59:59.000000"

        doc_list = frappe.get_all(
            self.reference_doctype,
            fields="name",
            filters=[
                {self.date_changed: (">=", reference_date_start)},
                {self.date_changed: ("<=", reference_date_end)},
            ],
        )

        for d in doc_list:
            doc = frappe.get_doc(self.reference_doctype, d.name)
            self.send_template_message(doc)
            # print(doc.name)


@frappe.whitelist()
def call_trigger_notifications():
    """Trigger notifications."""
    try:
        # Directly call the trigger_notifications function
        trigger_notifications()  
    except Exception as e:
        # Log the error but do not show any popup or alert
        frappe.log_error(frappe.get_traceback(), "Error in call_trigger_notifications")
        # Optionally, you could raise the exception to be handled elsewhere if needed
        raise e

def trigger_notifications(method="daily"):
    if frappe.flags.in_import or frappe.flags.in_patch:
        # don't send notifications while syncing or patching
        return

    if method == "daily":
        doc_list = frappe.get_all(
            "WhatsApp Notification", filters={"doctype_event": ("in", ("Days Before", "Days After")), "disabled": 0}
        )
        for d in doc_list:
            alert = frappe.get_doc("WhatsApp Notification", d.name)
            alert.get_documents_for_today()
           
