import frappe
import json
from frappe import _

def validate(doc, method):
    if doc.type == "Incoming" and doc.get("from"):
        name, doctype = get_lead_from_number(doc.get("from"))
        doc.reference_doctype = doctype
        doc.reference_name = name

def on_update(doc, method):
    try:
        frappe.publish_realtime(
            "whatsapp_message",
            {
                "reference_doctype": doc.reference_doctype,
                "reference_name": doc.reference_name,
                "from": doc.get("from"),
                "to": doc.get("to")
            },
        )
        notify_agent(doc)
    except Exception as e:
        frappe.log_error(f"Failed to send Whatsapp Message Event: {str(e)}", "WhatsApp Notification")

def notify_agent(doc):
    try:
        if doc.type != "Incoming" or not doc.reference_name or doc.reference_doctype != "Lead":
            return
        
        # Fetch the executive name directly from the Lead doctype
        executive = frappe.db.get_value("Lead", doc.reference_name, "executive")

        if not executive:
            return
        
        # Fetch the executive's email from the Executive doctype
        executive_email = frappe.db.get_value("Executive", executive, "email")

        if not executive_email:
            return
        
        def truncate_text(text, length=30):
            """Truncate text if it exceeds the given length."""
            return (text[:length] + '...') if text and len(text) > length else text
        
          # Determine message content based on content type
        content_type = doc.get("content_type")
        if content_type == "text":
            message_preview = truncate_text(doc.message)
        else:
            message_preview = f"[{content_type.capitalize()}]"
        
        # Prepare the notification message
        notification_text = f"""
            <div class="mb-2 leading-5 text-gray-600">
                <span>WhatsApp message from </span>
                <span class="font-medium text-gray-900"><strong>{doc.reference_name}</strong></span>
                <span>: {message_preview}</span>
            </div>
        """

        # Function to create Notification Log
        def create_notification(user):
            try:
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": notification_text,
                    "document_type": "Lead",
                    "document_name": doc.reference_name,
                    "for_user": user,
                    "type": "Alert"
                }).insert(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Failed to create notification for {user}: {str(e)}", "WhatsApp Notification")

        # Send notification to Executive if email exists
        if executive_email:
            create_notification(executive_email)

        # Always notify Administrator
        # create_notification("info@hairfreehairgrow.com")

        # Ensure database changes are saved
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to notify Executive/Administrator: {str(e)}", "WhatsApp Notification")

def get_lead_from_number(number):
    """Get lead from the given number using Query Builder."""
    mobile_no = parse_mobile_no(number)
    query = """
        SELECT name, contact_number, executive
        FROM `tabLead`
        WHERE status != 'Duplicate Lead'
        AND REPLACE(REPLACE(REPLACE(contact_number, ' ', ''), '-', ''), '+', '') LIKE %(mobile_no)s
        ORDER BY creation DESC
        LIMIT 1
    """

    lead = frappe.db.sql(query, {"mobile_no": f"%{mobile_no}%"}, as_dict=True)

    if lead:
        lead_name = lead[0].get("name")
        return lead_name, "Lead"

    return None, None

def parse_mobile_no(mobile_no: str):
    """Parse mobile number to remove spaces, brackets, etc.
    >>> parse_mobile_no('+91 (766) 667 6666')
    ... '+917666676666'
    """
    return "".join([c for c in mobile_no if c.isdigit()])


@frappe.whitelist()
def is_whatsapp_enabled():
    if not frappe.db.exists("DocType", "WhatsApp Settings"):
        return False
    return frappe.get_cached_value("WhatsApp Settings", "WhatsApp Settings", "enabled")

@frappe.whitelist()
def is_whatsapp_installed():
    if not frappe.db.exists("DocType", "WhatsApp Settings"):
        return False
    return True


@frappe.whitelist()
def get_whatsapp_messages(reference_doctype = None, reference_name = None, phone = None):
    if not frappe.db.exists("DocType", "WhatsApp Message"):
        return []
    messages = []

    filters = {}

    if reference_doctype and reference_name:
        filters = {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
        }

    or_filters = None
    if phone:
        # filter OR to check phone in to and from field
        or_filters = [
            {"from": phone},
            {"to": phone}
        ] 

    messages += frappe.get_all(
        "WhatsApp Message",
        filters=filters,
        or_filters= or_filters if or_filters else None,
        fields=[
            "name",
            "type",
            "to",
            "from",
            "content_type",
            "message_type",
            "attach",
            "template",
            "use_template",
            "message_id",
            "is_reply",
            "reply_to_message_id",
            "creation",
            "message",
            "status",
            "reference_doctype",
            "reference_name",
            "template_parameters",
            "template_header_parameters",
        ],
    )

    # Filter messages to get only Template messages
    template_messages = [
        message for message in messages if message["message_type"] == "Template"
    ]

    # Iterate through template messages
    for template_message in template_messages:
        # Find the template that this message is using
        template = frappe.get_doc("WhatsApp Templates", template_message["template"])

        # If the template is found, add the template details to the template message
        if template:
            template_message["template_name"] = template.template_name
            if template_message["template_parameters"]:
                parameters = json.loads(template_message["template_parameters"])
                template.template = parse_template_parameters(
                    template.template, parameters
                )

            template_message["template"] = template.template
            if template_message["template_header_parameters"]:
                header_parameters = json.loads(
                    template_message["template_header_parameters"]
                )
                template.header = parse_template_parameters(
                    template.header, header_parameters
                )
            template_message["header"] = template.header
            template_message["footer"] = template.footer

    # Filter messages to get only reaction messages
    reaction_messages = [
        message for message in messages if message["content_type"] == "reaction"
    ]

    # Iterate through reaction messages
    for reaction_message in reaction_messages:
        # Find the message that this reaction is reacting to
        reacted_message = next(
            (
                m
                for m in messages
                if m["message_id"] == reaction_message["reply_to_message_id"]
            ),
            None,
        )

        # If the reacted message is found, add the reaction to it
        if reacted_message:
            reacted_message["reaction"] = reaction_message["message"]

    for message in messages:
        from_name = get_from_name(message) if message["from"] else _("You")
        message["from_name"] = from_name
    # Filter messages to get only replies
    reply_messages = [message for message in messages if message["is_reply"]]

    # Iterate through reply messages
    for reply_message in reply_messages:
        # Find the message that this message is replying to
        replied_message = next(
            (
                m
                for m in messages
                if m["message_id"] == reply_message["reply_to_message_id"]
            ),
            None,
        )

        # If the replied message is found, add the reply details to the reply message
        from_name = (
            get_from_name(reply_message) if replied_message["from"] else _("You")
        )
        if replied_message:
            message = replied_message["message"]
            if replied_message["message_type"] == "Template":
                message = replied_message["template"]
            reply_message["reply_message"] = message
            reply_message["header"] = replied_message.get("header") or ""
            reply_message["footer"] = replied_message.get("footer") or ""
            reply_message["reply_to"] = replied_message["name"]
            reply_message["reply_to_type"] = replied_message["type"]
            reply_message["reply_to_from"] = from_name

    return [message for message in messages if message["content_type"] != "reaction"]

@frappe.whitelist()
def create_whatsapp_message(
    reference_doctype,
    reference_name,
    message,
    to,
    attach,
    reply_to,
    content_type="text",
):
    doc = frappe.new_doc("WhatsApp Message")

    if reply_to:
        reply_doc = frappe.get_doc("WhatsApp Message", reply_to)
        doc.update(
            {
                "is_reply": True,
                "reply_to_message_id": reply_doc.message_id,
            }
        )

    doc.update(
        {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "message": message or attach,
            "to": to,
            "attach": attach,
            "content_type": content_type,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name

@frappe.whitelist()
def send_whatsapp_template(reference_doctype, reference_name, template, to):
    doc = frappe.new_doc("WhatsApp Message")
    doc.update(
        {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "message_type": "Template",
            "message": "Template message",
            "content_type": "text",
            "use_template": True,
            "template": template,
            "to": to,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name

@frappe.whitelist()
def react_on_whatsapp_message(emoji, reply_to_name):
    reply_to_doc = frappe.get_doc("WhatsApp Message", reply_to_name)
    to = reply_to_doc.type == "Incoming" and reply_to_doc.get("from") or reply_to_doc.to
    doc = frappe.new_doc("WhatsApp Message")
    doc.update(
        {
            "reference_doctype": reply_to_doc.reference_doctype,
            "reference_name": reply_to_doc.reference_name,
            "message": emoji,
            "to": to,
            "reply_to_message_id": reply_to_doc.message_id,
            "content_type": "reaction",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name

def parse_template_parameters(string, parameters):
    for i, parameter in enumerate(parameters, start=1):
        placeholder = "{{" + str(i) + "}}"
        string = string.replace(placeholder, parameter)

    return string

def get_from_name(message):
    if not message["reference_doctype"] or not message["reference_name"]:
        return "Anonymous User"
    doc = frappe.get_doc(message["reference_doctype"], message["reference_name"])
    from_name = ""
    if message["reference_doctype"] == "Lead":
        from_name = doc.get("full_name") or doc.get("first_name") or doc.get("name")
    else:
        from_name = doc.get("first_name", "Anonymous User") + " " + doc.get("last_name", "")
    return from_name

@frappe.whitelist()
def get_form_data():
    executive=frappe.get_all("Executive",fields=["*"],as_dict=True)