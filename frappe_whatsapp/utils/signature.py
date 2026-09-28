"""Verify that a webhook request really came from Meta.

Meta signs every webhook POST (messages, statuses, template updates, Flow data exchange)
with the app secret of the Meta app: header ``X-Hub-Signature-256`` carries
``sha256=`` + hex HMAC-SHA256(app_secret, raw request body).

The endpoints that receive those calls are guest endpoints, so without this check
anyone who knows the URL can create WhatsApp Messages, Notification Logs and Flow
data on the site. Requests are therefore refused unless the signature matches the
App Secret of an active WhatsApp Account. Sites that cannot configure the secret yet
can opt out with the site config key ``whatsapp_allow_unsigned_webhooks: 1``.
"""

import hashlib
import hmac

import frappe

SIGNATURE_HEADER = "X-Hub-Signature-256"
ALLOW_UNSIGNED_KEY = "whatsapp_allow_unsigned_webhooks"


def signature_matches(body, header, secrets):
	"""True if ``header`` is a valid Meta signature of ``body`` under any of ``secrets``."""
	if not header or not header.startswith("sha256="):
		return False
	received = header[len("sha256="):].strip().lower()
	if isinstance(body, str):
		body = body.encode()
	for secret in secrets:
		if not secret:
			continue
		expected = hmac.new(secret.encode(), body or b"", hashlib.sha256).hexdigest()
		if hmac.compare_digest(received, expected):
			return True
	return False


def get_app_secrets():
	"""App secrets of all active WhatsApp Accounts that have one."""
	from frappe.utils.password import get_decrypted_password

	secrets = []
	for name in frappe.get_all("WhatsApp Account", filters={"status": "Active"}, pluck="name"):
		secret = get_decrypted_password("WhatsApp Account", name, "app_secret", raise_exception=False)
		if secret:
			secrets.append(secret)
	return secrets


def is_verified_meta_request():
	"""Check the current request's signature. Never writes to the database, so a
	flood of forged requests cannot fill it."""
	secrets = get_app_secrets()
	if not secrets:
		if frappe.conf.get(ALLOW_UNSIGNED_KEY):
			return True
		frappe.logger("frappe_whatsapp").warning(
			"WhatsApp webhook refused: no active WhatsApp Account has an App Secret "
			f"(set one, or set site config {ALLOW_UNSIGNED_KEY}=1 to accept unsigned calls)"
		)
		return False
	body = frappe.request.get_data(cache=True)
	return signature_matches(body, frappe.request.headers.get(SIGNATURE_HEADER), secrets)


def forbidden():
	from werkzeug.wrappers import Response

	return Response("Invalid or missing X-Hub-Signature-256", status=403)
