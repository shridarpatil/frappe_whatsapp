"""Create whatsapp template."""

# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import re
import frappe
import magic
import requests
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request, make_request
from requests.exceptions import HTTPError, RequestException

from frappe_whatsapp.utils import get_whatsapp_account

# Fields Meta actually stores on a template. Editing anything else (for_doctype /
# field_names are internal to this app) must NOT trigger a Meta edit + re-review.
# See SRO-2026-10-00228.
META_STORED_FIELDS = (
    "template",
    "sample_values",
    "header_type",
    "header",
    "sample",
    "footer",
    "buttons",
)

class WhatsAppTemplates(Document): 
    """Create whatsapp template."""

    def before_insert(self):
        # language_code is part of the name ({template_name}-{language_code}) and
        # Frappe sets the name before validate(), so it must be filled here.
        self.set_language_code()

    def validate(self):
        self.set_whatsapp_account()
        self.validate_sample_values()
        self.validate_media_header()

        if not self.language_code or self.has_value_changed("language"):
            lang_code = frappe.db.get_value("Language", self.language) or "en"
            self.language_code = lang_code.replace("-", "_")
        self.set_language_code()

        meta_changed = not self.is_new() and self._meta_fields_changed()

        # Upload the header sample to Meta only when it is actually needed
        if self.header_type in ["IMAGE", "DOCUMENT"] and self.sample:
            if self.is_new() or self.has_value_changed("sample") or (meta_changed and not self.header_media_handle):
                self.get_session_id(self.sample)
                self.get_media_id(self.sample)
                self.header_media_handle = self._media_id
            elif self.header_media_handle:
                self._media_id = self.header_media_handle

        # On update, call Meta only when a Meta-stored field changed.
        if meta_changed:
            self.update_template()

    def validate_sample_values(self):
        """Block malformed BODY sample values before they reach Meta.

        Meta builds the BODY example from a comma-separated ``sample_values`` list
        that must match the ``{{n}}`` placeholders in the body. Values on separate
        lines, a comma inside a value, or a count mismatch were previously sent as-is
        and rejected by Meta with an opaque error (SRO-2026-08-00159).
        """
        body = self.template or ""
        distinct = sorted({int(x) for x in re.findall(r"\{\{\s*(\d+)\s*\}\}", body)})
        n = len(distinct)
        example = "Ravi,10 AM,04 Oct 2026 07:24 PM"

        # Placeholders must be numbered 1..n with no gaps.
        if distinct and distinct != list(range(1, n + 1)):
            found = ", ".join("{{" + str(d) + "}}" for d in distinct)
            frappe.throw(
                _("Template variables must be numbered sequentially starting at {{1}} with no gaps.")
                + " " + _("Found: {0}").format(found)
            )

        raw = self.sample_values or ""

        # No variables -> Sample Values must be empty. Normalise whitespace-only
        # input to "" so after_insert/update_template don't treat it as truthy
        # and send an invalid BODY example.
        if n == 0:
            if raw.strip():
                frappe.throw(_("The template body has no variables, so Sample Values must be empty."))
            self.sample_values = ""
            return

        # Sample Values must be a single comma-separated line.
        if "\n" in raw or "\r" in raw:
            frappe.throw(
                _("Sample Values must be on a single line.")
                + " " + _("Write one value per variable, separated by commas. Example: {0}").format(example)
            )

        values = [v.strip() for v in raw.split(",")]

        # Count must match the number of variables, with no empty values.
        if not raw.strip() or len(values) != n or any(v == "" for v in values):
            got = len(values) if raw.strip() else 0
            frappe.throw(
                _("The template has {0} variable(s) but Sample Values has {1}.").format(n, got)
                + " " + _(
                    "Write one value per variable on one line, separated by commas "
                    "(no comma inside a value). Example: {0}"
                ).format(example)
            )

        # Trim and canonicalise so the stored value matches what is sent to Meta.
        self.sample_values = ",".join(values)

    def validate_media_header(self):
        """A DOCUMENT/IMAGE header needs a sample file.

        Meta reviews that sample and it yields the media handle used to build the
        header component. Without it ``get_header()`` raised
        ``AttributeError: ... '_media_id'`` (SRO-2026-10-00227); show a clear,
        fixable message instead.
        """
        if self.header_type in ["IMAGE", "DOCUMENT"] and not self.sample:
            frappe.throw(
                _("Header Type {0} needs a sample file for Meta review. Attach one in Sample.").format(
                    self.header_type
                )
            )

    @staticmethod
    def _button_signature(buttons):
        """Return the Meta-relevant values of each button, order-sensitive.

        ``has_value_changed`` cannot be used on the ``buttons`` child table: it
        compares freshly-loaded child Document instances by identity (no value
        ``__eq__``), so it reports a change on every save. Compare these values
        instead.
        """
        return [
            (
                b.button_type,
                b.button_label,
                b.url_type,
                b.website_url,
                b.example_url,
                b.phone_number,
            )
            for b in (buttons or [])
        ]

    def _meta_fields_changed(self):
        """True if any field Meta stores changed vs the last saved version.

        Scalar fields use ``has_value_changed``; the ``buttons`` child table is
        compared by value so a no-op or internal-only save of a template that has
        buttons does not trigger a needless Meta edit + re-review
        (SRO-2026-10-00228).
        """
        if any(self.has_value_changed(f) for f in META_STORED_FIELDS if f != "buttons"):
            return True
        before = self.get_doc_before_save()
        before_buttons = before.buttons if before else []
        return self._button_signature(self.buttons) != self._button_signature(before_buttons)

    def _raise_meta_error(self, exc):
        """Surface Meta's real error on both create and edit; never hide it.

        A 4xx/5xx leaves the response on ``frappe.flags.integration_request`` (so we
        can read Meta's ``error_user_*``); a connection/timeout raises before the
        flag is set, so report that as an unreachable-Meta message rather than
        crashing with ``'NoneType' object has no attribute 'json'``
        (SRO-2026-10-00228).
        """
        if isinstance(exc, HTTPError) and frappe.flags.integration_request is not None:
            try:
                res = (frappe.flags.integration_request.json() or {}).get("error", {})
            except Exception:
                res = {}
            if res:
                frappe.throw(
                    msg=res.get("error_user_msg") or res.get("message") or str(exc),
                    title=res.get("error_user_title") or _("WhatsApp Error"),
                )
        if isinstance(exc, RequestException):
            frappe.throw(_("Could not reach Meta: {0}. Nothing was saved.").format(str(exc)))
        raise exc

    def set_whatsapp_account(self):
        """Set whatsapp account to default if missing"""
        if not self.whatsapp_account:
            default_whatsapp_account = get_whatsapp_account()
            if not default_whatsapp_account:
                frappe.throw(frappe._("Please set a default outgoing WhatsApp Account or Select available WhatsApp Account"))
            else:
                self.whatsapp_account = default_whatsapp_account.name

    def set_language_code(self):
        """Set language_code (Meta's format, e.g. en_US) from the selected Language."""
        if not self.language_code or self.has_value_changed("language"):
            lang_code = frappe.db.get_value("Language", self.language) or "en"
            self.language_code = lang_code.replace("-", "_")

    def get_session_id(self, file):
        """Upload media."""
        self.get_settings()

        # Check if it's a remote file, load data accordingly
        if file.startswith(('http://', 'https://')):
            remote_file_data = self._prepare_remote_file(file)
            file_type = remote_file_data['file_type']
            file_length = remote_file_data['file_size']
        else:
            file_content = self._read_local_file(file)
            mime = magic.Magic(mime=True)
            file_type = mime.from_buffer(file_content)
            file_length = len(file_content)

        payload = {
            'file_length': file_length,
            'file_type': file_type,
            'messaging_product': 'whatsapp'
        }

        response = make_post_request(
            f"{self._url}/{self._version}/{self._app_id}/uploads",
            headers=self._headers,
            data=json.loads(json.dumps(payload))
        )
        self._session_id = response['id']

    def _prepare_remote_file(self, file_url):
        """Download and return remote file content from URL."""
        try:
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            file_content = response.content
            file_size = len(file_content)
            
            # Get MIME type from Content-Type header or detect from content
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
            if content_type:
                file_type = content_type
            else:
                # Fallback to magic detection from content
                mime = magic.Magic(mime=True)
                file_type = mime.from_buffer(file_content)
            
            return {
                'file_content': file_content,
                'file_size': file_size,
                'file_type': file_type
            }
        except Exception as e:
            frappe.throw(f"Failed to download file from URL: {str(e)}")

    def get_media_id(self, file):
        self.get_settings()

        headers = {
                "authorization": f"OAuth {self._token}"
            }
        
        # Check if it's a remote file, load data accordingly
        if file.startswith(('http://', 'https://')):
            remote_file_data = self._prepare_remote_file(file)
            file_content = remote_file_data['file_content']
        else:
            file_content = self._read_local_file(file)

        payload = file_content
        response = make_post_request(
            f"{self._url}/{self._version}/{self._session_id}",
            headers=headers,
            data=payload
        )

        self._media_id = response['h']

    def _read_local_file(self, file_url):
        # Routed through File so path resolution stays inside Frappe's
        # vetted file handling — never feed a raw URL to open().
        return frappe.get_doc("File", {"file_url": file_url}).get_content()


    def after_insert(self):  # nosemgrep: frappe-modifying-but-not-committing -- self.actual_name/id/status are persisted via self.db_update() after the Meta round-trip; the static check can't trace through the API call
        # actual_name / id / status are persisted via self.db_update() below
        # after the Meta round-trip; the static check can't trace that call.
        if self.template_name:
            self.actual_name = self.template_name.lower().replace(" ", "_")  # nosemgrep: frappe-modifying-but-not-committing

        self.get_settings()
        data = {
            "name": self.actual_name,
            "language": self.language_code,
            "category": self.category,
            "components": [],
        }

        body = {
            "type": "BODY",
            "text": self.template,
        }
        if self.sample_values:
            body.update({"example": {"body_text": [self.sample_values.split(",")]}})

        data["components"].append(body)
        if self.header_type:
            data["components"].append(self.get_header())

        # add footer
        if self.footer:
            data["components"].append({"type": "FOOTER", "text": self.footer})

        # add buttons
        if self.buttons:
            button_block = {"type": "BUTTONS", "buttons": []}
            for btn in self.buttons:
                b = {"type": btn.button_type, "text": btn.button_label}

                if btn.button_type == "Visit Website":
                    b["type"] = "URL"
                    b["url"] = btn.website_url
                    if btn.url_type == "Dynamic" and btn.example_url:
                        b["example"] = btn.example_url.split(",")
                elif btn.button_type == "Call Phone":
                    b["type"] = "PHONE_NUMBER"
                    b["phone_number"] = btn.phone_number
                elif btn.button_type == "Quick Reply":
                    b["type"] = "QUICK_REPLY"
                elif btn.button_type == "Multi-Product Message":
                    b["type"] = "MPM"
                elif btn.button_type == "Catalog":
                    b["type"] = "CATALOG"

                button_block["buttons"].append(b)

            data["components"].append(button_block)

        try:
            response = make_post_request(
                f"{self._url}/{self._version}/{self._business_id}/message_templates",
                headers=self._headers,
                data=json.dumps(data),
            )
            self.id = response["id"]  # nosemgrep: frappe-modifying-but-not-committing
            self.status = response["status"]  # nosemgrep: frappe-modifying-but-not-committing
            self.db_update()
        except Exception as e:
            self._raise_meta_error(e)

    def update_template(self):
        """Update template to meta."""
        self.get_settings()
        data = {"components": []}

        body = {
            "type": "BODY",
            "text": self.template,
        }
        if self.sample_values:
            body.update({"example": {"body_text": [self.sample_values.split(",")]}})
        data["components"].append(body)
        if self.header_type:
            data["components"].append(self.get_header())
        if self.footer:
            data["components"].append({"type": "FOOTER", "text": self.footer})
        if self.buttons:
            button_block = {"type": "BUTTONS", "buttons": []}
            for btn in self.buttons:
                b = {"type": btn.button_type, "text": btn.button_label}

                if btn.button_type == "Visit Website":
                    b["type"] = "URL"
                    b["url"] = btn.website_url
                    if btn.url_type == "Dynamic" and btn.example_url:
                        b["example"] = btn.example_url.split(",")
                elif btn.button_type == "Call Phone":
                    b["type"] = "PHONE_NUMBER"
                    b["phone_number"] = btn.phone_number
                elif btn.button_type == "Quick Reply":
                    b["type"] = "QUICK_REPLY"
                elif btn.button_type == "Multi-Product Message":
                    b["type"] = "MPM"
                    # MPM buttons often require additional fields like catalog_id
                elif btn.button_type == "Catalog":
                    b["type"] = "CATALOG"

                button_block["buttons"].append(b)

            data["components"].append(button_block)

        try:
            # post template to meta for update
            make_post_request(
                f"{self._url}/{self._version}/{self.id}",
                headers=self._headers,
                data=json.dumps(data),
            )
        except Exception as e:
            self._raise_meta_error(e)

    def get_settings(self):
        """Get whatsapp settings."""
        # Underscore-prefixed attributes below are in-memory scratch for the
        # outbound HTTP call — they are not DocType fields and must not be
        # persisted. Semgrep's static check can't tell the difference.
        settings = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        self._token = settings.get_password("token")  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._url = settings.url  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._version = settings.version  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._business_id = settings.business_id  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._app_id = settings.app_id  # nosemgrep: frappe-modifying-but-not-committing-other-method

        self._headers = {  # nosemgrep: frappe-modifying-but-not-committing-other-method
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }

    def on_trash(self):
        self.get_settings()
        url = f"{self._url}/{self._version}/{self._business_id}/message_templates?name={self.actual_name}"
        try:
            make_request("DELETE", url, headers=self._headers)
        except Exception:
            res = frappe.flags.integration_request.json().get("error", {})
            if res.get("error_user_title") == "Message Template Not Found":
                frappe.msgprint(
                    "Deleted locally", res.get("error_user_title", "Error"), alert=True
                )
            else:
                frappe.throw(
                    msg=res.get("error_user_msg"),
                    title=res.get("error_user_title", "Error"),
                )

    def get_header(self):
        """Get header format."""
        header = {"type": "header", "format": self.header_type}
        if self.header_type == "TEXT":
            header["text"] = self.header
            if self.sample:
                samples = self.sample.split(", ")
                header.update({"example": {"header_text": samples}})
        else:
            media_handle = getattr(self, "_media_id", None) or self.header_media_handle
            header.update({"example": {"header_handle": [media_handle]}})

        return header

@frappe.whitelist()
def fetch():
    """Fetch templates from meta."""
    """Later improve this code to pass a whatsapp account remove the js funcation so that it is called from whatsapp account doctype """
    whatsapp_accounts = frappe.get_all('WhatsApp Account', filters={'status': 'Active'}, fields=['name', 'token', 'url', 'version', 'business_id'])

    for account in whatsapp_accounts:
        # get credentials
        token = frappe.get_doc("WhatsApp Account", account.name).get_password("token")
        url = account.url
        version = account.version
        business_id = account.business_id

        headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}

        try:
            for template in get_templates_from_meta(
                f"{url}/{version}/{business_id}/message_templates", headers
            ):
                # set flag to insert or update
                flags = 1
                # Meta keeps each language of a template separately, so match on both
                template_filters = {"actual_name": template["name"], "language_code": template["language"]}
                if frappe.db.exists("WhatsApp Templates", template_filters):
                    doc = frappe.get_doc("WhatsApp Templates", template_filters)
                else:
                    flags = 0
                    doc = frappe.new_doc("WhatsApp Templates")
                    doc.template_name = template["name"]
                    doc.actual_name = template["name"]

                doc.status = template["status"]
                doc.language_code = template["language"]
                doc.category = template["category"]
                doc.id = template["id"]
                doc.whatsapp_account = account.name

                # update components
                for component in template["components"]:

                    # update header
                    if component["type"] == "HEADER":
                        doc.header_type = component["format"]

                        # if format is text update sample text
                        if component["format"] == "TEXT":
                            doc.header = component["text"]
                    # Update footer text
                    elif component["type"] == "FOOTER":
                        doc.footer = component["text"]

                    # update template text
                    elif component["type"] == "BODY":
                        doc.template = component["text"]
                        if component.get("example"):
    			            # Check if 'body_text' exists before trying to access it
                            if component["example"].get("body_text"):
                                doc.sample_values = ",".join(
            	                    component["example"]["body_text"][0]
                    	        )

                    # Update buttons
                    elif component["type"] == "BUTTONS":
                        doc.set("buttons", [])
                        frappe.db.delete("WhatsApp Button", {"parent": doc.name, "parenttype": "WhatsApp Templates"})
                        typeMap = {
                            "URL": "Visit Website",
                            "PHONE_NUMBER": "Call Phone",
                            "QUICK_REPLY": "Quick Reply",
                            "FLOW": "Flow",
                            "MPM": "Multi-Product Message",
                            "CATALOG": "Catalog"
                        }

                        for i, button in enumerate(component.get("buttons", []), start=1):
                            btn_type_raw = button.get("type")
                            if btn_type_raw not in typeMap:
                                frappe.log_error("WhatsApp Fetch Error", f"Unknown WhatsApp Button Type: {btn_type_raw}")
                                continue

                            btn = {}
                            btn["button_type"] = typeMap[button["type"]]
                            btn["button_label"] = button.get("text")
                            btn["sequence"] = i

                            if button["type"] == "URL":
                                btn["website_url"] = button.get("url")
                                if "{{" in btn["website_url"]:
                                    btn["url_type"] = "Dynamic"
                                else:
                                    btn["url_type"] = "Static"

                                if button.get("example"):
                                    btn["example_url"] = ",".join(button["example"])
                            elif button["type"] == "PHONE_NUMBER":
                                btn["phone_number"] = button.get("phone_number")
                            elif button["type"] == "FLOW":
                                btn["flow"] = button.get("flow")

                            doc.append("buttons", btn)

                upsert_doc_without_hooks(doc, "WhatsApp Button", "buttons")

        except Exception as e:
            # Check if frappe.flags.integration_request is set and has a .json() method
            if hasattr(frappe.flags.integration_request, 'json'):
                try:
                    res = frappe.flags.integration_request.json().get("error", {})
                    error_message = res.get("error_user_msg", res.get("message"))
                    frappe.throw(
                        msg=error_message,
                        title=res.get("error_user_title", "Error"),
                    )
                except (json.JSONDecodeError, KeyError):
                    # Handle cases where the response is not valid JSON or lacks the 'error' key
                    frappe.throw(f"An unexpected error occurred while fetching templates: {e}")
            else:
                # Handle cases where frappe.flags.integration_request doesn't exist or isn't a proper response object
                frappe.throw(f"An unexpected server error occurred: {e}")

    return "Successfully fetched templates from meta"

def get_templates_from_meta(url, headers):
    """Yield every template from Meta, following paging.next until the last page."""
    while url:
        response = make_request("GET", url, headers=headers)
        yield from response["data"]
        url = response.get("paging", {}).get("next")

def upsert_doc_without_hooks(doc, child_dt, child_field):
    """Insert or update a parent document and its children without hooks."""
    if frappe.db.exists(doc.doctype, doc.name):
        doc.db_update()
        frappe.db.delete(child_dt, {"parent": doc.name, "parenttype": doc.doctype})
    else:
        doc.db_insert()
    for d in doc.get(child_field):
        d.parent = doc.name
        d.parenttype = doc.doctype
        d.parentfield = child_field
        d.db_insert()
