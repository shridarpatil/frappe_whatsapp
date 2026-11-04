# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, now_datetime


class WhatsAppNotificationLog(Document):
	@staticmethod
	def clear_old_logs(days=90):
		"""Delete WhatsApp Notification Log rows older than `days`.

		Registered with Frappe's Log Settings via the `default_log_clearing_doctypes`
		hook, so the daily log-cleanup job trims this audit log (default 90 days,
		editable under Log Settings). It is written on every notification send, so it
		grows fast; deleted in batches keyed on `creation` to avoid holding a long
		table lock or bloating the transaction on large backlogs.
		"""
		cutoff = add_to_date(now_datetime(), days=-cint(days))
		while True:
			names = frappe.get_all(
				"WhatsApp Notification Log",
				filters={"creation": ["<", cutoff]},
				pluck="name",
				order_by="creation asc",
				limit=10000,
			)
			if not names:
				break
			frappe.db.delete("WhatsApp Notification Log", {"name": ["in", names]})
			# nosemgrep: frappe-manual-commit -- batched cleanup runs inside the scheduled
			# log-clean-up job (outside request scope); commit each batch so table locks and
			# the undo log don't grow unbounded while deleting large backlogs.
			frappe.db.commit()
