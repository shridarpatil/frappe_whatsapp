# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request
from frappe.utils import cstr
from frappe.model.utils import get_fetch_values
from frappe.ui.form import Frm


class WhatsAppMessage(Document):
    """Send whats app messages."""

    def before_insert(self):
        """Send message."""
        if self.type == 'Outgoing' and self.message_type != 'Template':
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + '/'+ self.attach
            else:
                link = self.attach

            frm.set_df_property(self.to, 'options', ['option a', 'option b']);
            mobile_no = frappe.db.get_value("Customer", filters={"customer_name": customer_name}, fieldname="mobile_no")

            data = {
                "messaging_product": "whatsapp",
                "to": self.format_number(mobile_no),
                "type": self.content_type
            }
             
                         
            if self.content_type == "text":
                data["text"] = {
                    "preview_url": True,
                    "body": self.message
                }
            elif self.content_type == "image":
                data["image"] = {
                    "link": link,
                    "caption": self.message
                }
            elif self.content_type == "video":
                data["video"] = {
                    "link": link,
                    "caption": self.message
                }
            elif self.content_type == "audio":
                data["audio"] = {
                    "link": link,
                    "caption": self.message
                }
            elif self.content_type == "document":
                data["document"] = {
                    "link": link,
                    "filename": self.name,
                    "caption": self.message
                }

            try:
                self.notify(data)
                self.status = "Success"
            except Exception as e:
                self.status = "Failed"
                frappe.throw(f"Failed to send message {str(e)}")


    def notify(self, data):
        """Notify."""

        mobile_no = (self.to)
        customer_name = frappe.db.get_value("Customer", filters={"mobile_no": mobile_no}, fieldname="name")
        

        settings = frappe.get_doc(
            "WhatsApp Settings", "WhatsApp Settings",
        )
        token = settings.get_password("token")

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }
        try:
            response = make_post_request(
                f"{settings.url}/{settings.version}/{settings.phone_id}/messages",
                headers=headers, data=json.dumps(data)
            )
            self.message_id = response['messages'][0]['id']
            frappe.msgprint("Messaggio inviato a " + customer_name + "(" +str(self.format_number(self.to)) +")"+ "\n" + self.message, indicator="green", alert=True)

        except Exception as e:
            res = frappe.flags.integration_request.json()['error']
            error_message = res.get('Error', res.get("message"))
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": "Text Message",
                "meta_data": frappe.flags.integration_request.json()
            }).insert(ignore_permissions=True)

            frappe.throw(
                msg=error_message,
                title=res.get("error_user_title", "Error")
            )

    def format_number(self, number):
        """Format number."""
        if number.startswith("+"):
            number = number[1:len(number)]

        return number
