import os

import frappe
from frappe import _
from frappe.utils import cint

from frappe_whatsapp.utils import format_number

CHAT_ROLE = "WhatsApp Manager"

# The other party of a message: the sender of an incoming one, the recipient of an outgoing one.
NUMBER_SQL = "REPLACE(IF(m.type = 'Incoming', m.`from`, m.`to`), '+', '')"

MESSAGE_FIELDS = """
	m.name, m.type, m.message, m.content_type, m.attach, m.status, m.creation,
	m.message_id, m.is_reply, m.reply_to_message_id, m.template, m.message_type,
	m.profile_name
"""

MEDIA_TYPES = {
	"image": {"jpg", "jpeg", "png", "webp"},
	"video": {"mp4", "3gp"},
	"audio": {"aac", "amr", "mp3", "m4a", "ogg", "opus"},
}


def check_access(ptype="read"):
	"""Return True when the permission check should be skipped on insert."""
	if frappe.has_permission("WhatsApp Message", ptype):
		return False
	if CHAT_ROLE in frappe.get_roles():
		return True
	frappe.throw(_("Not permitted to use WhatsApp Chat"), frappe.PermissionError)


@frappe.whitelist()
def get_conversations(search=None, limit=200):
	check_access()

	conditions = ""
	values = {"limit": cint(limit) or 200}
	if search:
		conditions = "where (c.number like %(search)s or p.profile_name like %(search)s or c.last_profile like %(search)s)"
		values["search"] = f"%{search.strip().lstrip('+')}%"

	rows = frappe.db.sql(
		f"""
		select
			c.number, c.last_at, c.unread, c.last_profile,
			p.profile_name, p.contact,
			m.message, m.content_type, m.type, m.status
		from (
			select
				{NUMBER_SQL} as number,
				max(m.creation) as last_at,
				sum(m.type = 'Incoming' and ifnull(m.status, '') = '') as unread,
				max(if(m.type = 'Incoming', m.profile_name, null)) as last_profile
			from `tabWhatsApp Message` m
			where ifnull({NUMBER_SQL}, '') != ''
				and ifnull(m.content_type, '') != 'reaction'
			group by number
		) c
		join `tabWhatsApp Message` m on {NUMBER_SQL} = c.number and m.creation = c.last_at
		left join `tabWhatsApp Profiles` p on p.number = c.number
		{conditions}
		order by c.last_at desc
		limit %(limit)s
		""",
		values,
		as_dict=True,
	)

	conversations, seen = [], set()
	for row in rows:
		if row.number in seen:
			continue
		seen.add(row.number)
		row.title = row.profile_name or row.last_profile or f"+{row.number}"
		row.unread = cint(row.unread)
		conversations.append(row)

	return conversations


@frappe.whitelist()
def get_messages(number, before=None, limit=50):
	check_access()
	number = format_number(number)

	conditions = ""
	values = {"number": number, "limit": cint(limit) or 50}
	if before:
		conditions = "and m.creation < %(before)s"
		values["before"] = before

	messages = frappe.db.sql(
		f"""
		select {MESSAGE_FIELDS}
		from `tabWhatsApp Message` m
		where {NUMBER_SQL} = %(number)s {conditions}
		order by m.creation desc
		limit %(limit)s
		""",
		values,
		as_dict=True,
	)
	messages.reverse()

	profile = frappe.db.get_value(
		"WhatsApp Profiles", {"number": number}, ["name", "profile_name", "contact"], as_dict=True
	)

	return {"messages": messages, "profile": profile, "has_more": len(messages) == values["limit"]}


@frappe.whitelist()
def mark_as_read(number):
	check_access()
	number = format_number(number)

	unread = frappe.db.sql(
		f"""
		select m.name
		from `tabWhatsApp Message` m
		where {NUMBER_SQL} = %(number)s and m.type = 'Incoming' and ifnull(m.status, '') = ''
		order by m.creation desc
		""",
		{"number": number},
		pluck=True,
	)
	if not unread:
		return

	# One receipt for the latest message marks the whole conversation read on the phone.
	try:
		frappe.get_doc("WhatsApp Message", unread[0]).send_read_receipt()
	except Exception:
		frappe.log_error("WhatsApp Chat: read receipt failed")

	frappe.db.sql(
		"""update `tabWhatsApp Message` set status = 'marked as read'
		where name in %(names)s and ifnull(status, '') = ''""",
		{"names": tuple(unread)},
	)


@frappe.whitelist()
def send_message(number, message=None, attach=None):
	ignore_permissions = check_access("create")
	number = format_number(number)

	if not (message or "").strip() and not attach:
		frappe.throw(_("Type a message or attach a file"))

	# Reply from the account the conversation is already on.
	account = frappe.db.sql(
		f"""
		select m.whatsapp_account from `tabWhatsApp Message` m
		where {NUMBER_SQL} = %(number)s and ifnull(m.whatsapp_account, '') != ''
		order by m.creation desc limit 1
		""",
		{"number": number},
	)

	doc = frappe.get_doc(
		{
			"doctype": "WhatsApp Message",
			"type": "Outgoing",
			"to": number,
			"message": message,
			"attach": attach,
			"message_type": "Manual",
			"content_type": content_type_for(attach),
			"whatsapp_account": account[0][0] if account else None,
		}
	).insert(ignore_permissions=ignore_permissions)

	return frappe.db.sql(
		f"select {MESSAGE_FIELDS} from `tabWhatsApp Message` m where m.name = %s", doc.name, as_dict=True
	)[0]


def content_type_for(attach):
	if not attach:
		return "text"
	extension = os.path.splitext(attach.split("?")[0])[1].lstrip(".").lower()
	return next((kind for kind, extensions in MEDIA_TYPES.items() if extension in extensions), "document")
