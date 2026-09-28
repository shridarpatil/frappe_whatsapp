# Copyright (c) 2026, Shridhar Patil and Contributors
# See license.txt

import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe_whatsapp.testing import IntegrationTestCase

from frappe_whatsapp.utils.signature import ALLOW_UNSIGNED_KEY, signature_matches

SECRET = "test_app_secret_123"
ACCOUNT = "Test WA Signature Account"


def sign(body, secret=SECRET):
	return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestSignatureMatches(unittest.TestCase):
	"""Pure checks of the HMAC comparison."""

	body = b'{"entry": []}'

	def test_valid_signature(self):
		self.assertTrue(signature_matches(self.body, sign(self.body), [SECRET]))

	def test_uppercase_hex_accepted(self):
		self.assertTrue(signature_matches(self.body, sign(self.body).upper().replace("SHA256=", "sha256="), [SECRET]))

	def test_any_of_several_secrets(self):
		self.assertTrue(signature_matches(self.body, sign(self.body), ["other", SECRET]))

	def test_wrong_secret(self):
		self.assertFalse(signature_matches(self.body, sign(self.body, "wrong"), [SECRET]))

	def test_tampered_body(self):
		self.assertFalse(signature_matches(b'{"entry": [1]}', sign(self.body), [SECRET]))

	def test_missing_or_malformed_header(self):
		for header in (None, "", "abc", "sha1=" + sign(self.body)[7:]):
			self.assertFalse(signature_matches(self.body, header, [SECRET]))

	def test_no_secrets(self):
		self.assertFalse(signature_matches(self.body, sign(self.body), []))
		self.assertFalse(signature_matches(self.body, sign(self.body, ""), [""]))


class TestWebhookSignatureEnforced(IntegrationTestCase):
	"""The guest endpoints refuse unsigned or forged POSTs before writing anything."""

	payload = {
		"entry": [{
			"changes": [{
				"value": {
					"metadata": {"phone_number_id": "signature_test_phone_id"},
					"contacts": [{"profile": {"name": "Forger"}}],
					"messages": [{
						"from": "919900119999",
						"id": "wamid.signature_test_1",
						"type": "text",
						"text": {"body": "forged"},
					}],
				}
			}]
		}]
	}

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("WhatsApp Account", ACCOUNT):
			frappe.get_doc({
				"doctype": "WhatsApp Account",
				"account_name": ACCOUNT,
				"status": "Inactive",
				"url": "https://graph.facebook.com",
				"version": "v17.0",
				"phone_id": "signature_test_phone_id",
				"business_id": "signature_test_business_id",
				"app_id": "signature_test_app_id",
				"webhook_verify_token": "signature_test_verify_token",
			}).insert(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test fixture must be visible to later queries

	def setUp(self):
		# Only this account is active, so the result depends on its secret alone.
		self._active = frappe.get_all("WhatsApp Account", filters={"status": "Active"}, pluck="name")
		frappe.db.sql("UPDATE `tabWhatsApp Account` SET status='Inactive'")
		frappe.db.set_value("WhatsApp Account", ACCOUNT, {"status": "Active", "is_default_incoming": 1})
		self._conf = patch.dict(frappe.conf, {ALLOW_UNSIGNED_KEY: 0})
		self._conf.start()

	def tearDown(self):
		self._conf.stop()
		frappe.db.set_value("WhatsApp Account", ACCOUNT, "status", "Inactive")
		for name in self._active:
			frappe.db.set_value("WhatsApp Account", name, "status", "Active")
		for name in frappe.get_all("WhatsApp Message", filters={"message_id": ["like", "wamid.signature_test_%"]}, pluck="name"):
			frappe.delete_doc("WhatsApp Message", name, force=True)
		for name in frappe.get_all("WhatsApp Notification Log", filters={"template": "Webhook"}, pluck="name"):
			frappe.delete_doc("WhatsApp Notification Log", name, force=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- test cleanup

	def _set_secret(self, secret):
		from frappe.utils.password import remove_encrypted_password, set_encrypted_password

		if secret:
			set_encrypted_password("WhatsApp Account", ACCOUNT, secret, "app_secret")
		else:
			remove_encrypted_password("WhatsApp Account", ACCOUNT, "app_secret")

	def _post(self, signature=None, body=None):
		body = body if body is not None else json.dumps(self.payload).encode()
		request = MagicMock()
		request.method = "POST"
		request.get_data.return_value = body
		request.headers = {"X-Hub-Signature-256": signature} if signature else {}
		frappe.local.form_dict = frappe._dict(json.loads(body))
		with patch("frappe_whatsapp.utils.webhook.frappe.request", request), \
				patch("frappe_whatsapp.utils.signature.frappe.request", request):
			from frappe_whatsapp.utils.webhook import webhook
			return webhook()

	def _written(self):
		return (frappe.db.exists("WhatsApp Message", {"message_id": "wamid.signature_test_1"}),
				frappe.get_all("WhatsApp Notification Log", filters={"template": "Webhook"}))

	def test_refused_when_no_secret_configured(self):
		self._set_secret(None)
		response = self._post(signature=sign(json.dumps(self.payload).encode()))
		self.assertEqual(response.status_code, 403)
		message, logs = self._written()
		self.assertFalse(message)
		self.assertFalse(logs)

	def test_unsigned_refused(self):
		self._set_secret(SECRET)
		response = self._post()
		self.assertEqual(response.status_code, 403)
		self.assertEqual(self._written(), (None, []))

	def test_forged_signature_refused(self):
		self._set_secret(SECRET)
		response = self._post(signature=sign(json.dumps(self.payload).encode(), "attacker"))
		self.assertEqual(response.status_code, 403)
		self.assertEqual(self._written(), (None, []))

	def test_valid_signature_processed(self):
		self._set_secret(SECRET)
		body = json.dumps(self.payload).encode()
		self._post(signature=sign(body), body=body)
		message, logs = self._written()
		self.assertTrue(message)
		self.assertTrue(logs)

	def test_opt_out_accepts_unsigned(self):
		self._set_secret(None)
		with patch.dict(frappe.conf, {ALLOW_UNSIGNED_KEY: 1}):
			self._post()
		self.assertTrue(self._written()[0])
