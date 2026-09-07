# Copyright (c) 2026, GlobalSync ERP Software Solutions and Contributors
# See license.txt

"""`category` on a WhatsApp Templates row is a cache of a value only Meta owns.

Until this change it was a write-once copy of what *we submitted* and never of what Meta
*decided*. Two independent gaps kept it that way: the create path never read `category`
back off the response, and the app was not subscribed to `template_category_update`, so a
correct value would go stale the first time Meta re-categorised after approval.

Observed live on Blue Anvil prod (WABA 27935806516059749): all six templates submitted as
UTILITY on 2026-08-28; Meta re-categorised `gym_renewal_reminder` to MARKETING because its
body asks the member to renew. Our row still said UTILITY. Nothing noticed.

The consequence that sets the priority is **consent**, not cost. Marketing templates may
only go to members who have not opted out, so a row claiming UTILITY while Meta governs
the template as MARKETING is exactly the state in which a marketing message is sent to an
opted-out member in the belief that it is transactional.

Note the app was already internally inconsistent about this: `fetch()` has always done
`doc.category = template["category"]`. The pull path was right; the create and push paths
were missing.
"""

from unittest.mock import patch

import frappe
from frappe_whatsapp.testing import IntegrationTestCase

from frappe_whatsapp.utils.webhook import update_status, update_template_category

ACCOUNT = "Test WA Category Account"


class TestTemplateCategoryWebhook(IntegrationTestCase):
    """`template_category_update` — the steady-state path.

    This is the only mechanism that catches a re-categorisation of an *already approved*
    template, which per Meta's docs happens on a recurring sweep and not only at review.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("WhatsApp Account", ACCOUNT):
            account = frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": ACCOUNT,
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "category_test_phone_id",
                "business_id": "category_test_business_id",
                "app_id": "category_test_app_id",
                "webhook_verify_token": "category_test_verify_token",
            })
            account.insert(ignore_permissions=True)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- fixture must be visible to later queries

    def _template(self, actual_name, *, template_id=None, category="UTILITY", language_code="en"):
        name = f"{actual_name}__{language_code}-{language_code}"
        # Raw deletes, never `frappe.delete_doc`: `WhatsApp Templates.on_trash` makes a
        # real HTTP DELETE to graph.facebook.com. A test must not reach Meta.
        frappe.db.delete("WhatsApp Templates", {"name": name})
        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            # `template_name` carries a unique index while `actual_name` does not, so a
            # site holding one template in two languages must differ here. Worth knowing:
            # `fetch()` writes Meta's name into *both*, so it cannot in fact hold the same
            # template twice. The name+language filter is still the right one — narrowing
            # on the language it was told about is correct whether or not a second row
            # exists — and this is the shape that would break it if it were not.
            "template_name": f"{actual_name}__{language_code}",
            "actual_name": actual_name,
            "template": "Hi {{1}}, your membership expires on {{2}}.",
            "category": category,
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": language_code,
            "whatsapp_account": ACCOUNT,
            "status": "APPROVED",
            "id": template_id,
        })
        doc.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- fixture must be visible to later queries
        self.addCleanup(frappe.db.delete, "WhatsApp Templates", {"name": doc.name})
        return doc.name

    def _category(self, row):
        return frappe.db.get_value("WhatsApp Templates", row, "category")

    # ---- the observed incident ------------------------------------------

    def test_a_recategorisation_is_written_back(self):
        """The Blue Anvil case exactly: submitted UTILITY, Meta says MARKETING."""
        row = self._template("gym_renewal_reminder_cat", template_id="cat_id_001")

        update_template_category({
            "message_template_id": "cat_id_001",
            "message_template_name": "gym_renewal_reminder_cat",
            "message_template_language": "en",
            "previous_category": "UTILITY",
            "new_category": "MARKETING",
        })

        self.assertEqual(self._category(row), "MARKETING")

    def test_the_event_is_routed_from_update_status(self):
        """`update_status` is the fan-out the endpoint reaches — a handler nothing routes
        to would pass every test here and never run in production."""
        row = self._template("gym_routed_cat", template_id="cat_id_002")

        update_status({
            "field": "template_category_update",
            "value": {
                "message_template_id": "cat_id_002",
                "new_category": "MARKETING",
            },
        })

        self.assertEqual(self._category(row), "MARKETING")

    # ---- matching ---------------------------------------------------------

    def test_a_row_with_no_id_is_matched_by_name_and_language(self):
        """Not defensive padding — a required path. Rows seeded locally, or created
        before a real Meta submission, carry `id = null` and are unmatchable by id. All
        six Blue Anvil rows were in that state as recently as 2026-08-26 (#655)."""
        row = self._template("gym_unsubmitted_cat", template_id=None)

        update_template_category({
            "message_template_name": "gym_unsubmitted_cat",
            "message_template_language": "en",
            "new_category": "MARKETING",
        })

        self.assertEqual(self._category(row), "MARKETING")

    def test_the_language_narrows_the_name_match(self):
        """Two rows can share `actual_name` and differ only by language."""
        english = self._template("gym_multilang_cat", template_id=None, language_code="en")
        nepali = self._template("gym_multilang_cat", template_id=None, language_code="ne")

        update_template_category({
            "message_template_name": "gym_multilang_cat",
            "message_template_language": "ne",
            "new_category": "MARKETING",
        })

        self.assertEqual(self._category(nepali), "MARKETING")
        self.assertEqual(self._category(english), "UTILITY")

    def test_the_id_wins_when_both_could_match(self):
        row = self._template("gym_idwins_cat", template_id="cat_id_003")
        other = self._template("gym_idwins_other_cat", template_id="cat_id_004")

        update_template_category({
            "message_template_id": "cat_id_004",
            "message_template_name": "gym_idwins_cat",
            "new_category": "MARKETING",
        })

        self.assertEqual(self._category(other), "MARKETING")
        self.assertEqual(self._category(row), "UTILITY")

    # ---- the shapes that must not write ------------------------------------

    def test_an_unchanged_category_is_a_quiet_no_op(self):
        row = self._template("gym_noop_cat", template_id="cat_id_005", category="UTILITY")

        with patch.object(frappe, "log_error") as logged:
            update_template_category({
                "message_template_id": "cat_id_005",
                "previous_category": "UTILITY",
                "new_category": "UTILITY",
            })

        self.assertEqual(self._category(row), "UTILITY")
        logged.assert_not_called()

    def test_a_missing_new_category_writes_nothing_and_says_so(self):
        """The payload's field names come from Meta's docs, not from a delivery we have
        observed. If the documented key is absent, the row must keep its value and
        somebody has to be told the shape was wrong — never write None over a good
        cached value."""
        row = self._template("gym_nokey_cat", template_id="cat_id_006")

        with patch.object(frappe, "log_error") as logged:
            update_template_category({"message_template_id": "cat_id_006", "previous_category": "UTILITY"})

        self.assertEqual(self._category(row), "UTILITY")
        logged.assert_called_once()

    def test_the_advance_notice_variant_does_not_write_early(self):
        """Meta sends `correct_category` to announce a change it intends to apply later.
        Writing it would put a category into the row before it is in force — the same
        wrong-by-one-state problem this fix exists to close, in the other direction."""
        row = self._template("gym_advance_cat", template_id="cat_id_007")

        update_template_category({
            "message_template_id": "cat_id_007",
            "correct_category": "MARKETING",
        })

        self.assertEqual(self._category(row), "UTILITY")

    def test_an_unknown_template_is_not_created(self):
        """A template we do not hold is one this site does not send. Inventing a row from
        a webhook would put a half-populated template in front of staff."""
        before = frappe.db.count("WhatsApp Templates")

        with patch.object(frappe, "log_error") as logged:
            update_template_category({
                "message_template_id": "cat_id_does_not_exist",
                "message_template_name": "not_ours",
                "new_category": "MARKETING",
            })

        self.assertEqual(frappe.db.count("WhatsApp Templates"), before)
        logged.assert_called_once()

    def test_an_unknown_field_stays_a_quiet_ignore(self):
        """The Meta subscription is app-wide, so a newly ticked field goes live for every
        tenant at once — including tenants still on an older image. An unhandled event has
        to be a no-op, not an error log on every delivery across the fleet."""
        with patch.object(frappe, "log_error") as logged:
            update_status({"field": "some_future_meta_field", "value": {"anything": 1}})

        logged.assert_not_called()


class TestTemplateCategoryWriteBack(IntegrationTestCase):
    """The create and update paths, which submitted a category and never read one back.

    `after_insert` stored only `id` and `status`; `update_template` discarded its response
    entirely. So a template Meta accepted under a different category than requested kept
    our submitted value silently, from birth.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("WhatsApp Account", ACCOUNT):
            frappe.get_doc({
                "doctype": "WhatsApp Account",
                "account_name": ACCOUNT,
                "status": "Active",
                "url": "https://graph.facebook.com",
                "version": "v17.0",
                "phone_id": "category_test_phone_id",
                "business_id": "category_test_business_id",
                "app_id": "category_test_app_id",
                "webhook_verify_token": "category_test_verify_token",
            }).insert(ignore_permissions=True)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit -- fixture must be visible to later queries
    def setUp(self):
        # Per test, not once per class: `get_settings` reads this inside the transaction
        # each test runs in, and the class-level fixture is outside it. Same reason
        # test_webhook.py does it this way.
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("WhatsApp Account", ACCOUNT, "category_token", "token")

    def _row(self, actual_name, *, category="UTILITY", template_id=None):
        name = f"{actual_name}-en"
        # See the note in TestTemplateCategoryWebhook: on_trash calls out to Meta.
        frappe.db.delete("WhatsApp Templates", {"name": name})
        doc = frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": actual_name,
            "actual_name": actual_name,
            "template": "Hi {{1}}, your membership expires on {{2}}.",
            "category": category,
            "language": frappe.db.get_value("Language", {"language_code": "en"}) or "en",
            "language_code": "en",
            "whatsapp_account": ACCOUNT,
            "status": "PENDING",
            "id": template_id,
        })
        doc.db_insert()
        frappe.db.commit()  # nosemgrep: frappe-manual-commit -- fixture must be visible to later queries
        self.addCleanup(frappe.db.delete, "WhatsApp Templates", {"name": doc.name})
        return frappe.get_doc("WhatsApp Templates", doc.name)

    # ---- create -----------------------------------------------------------

    def test_the_category_meta_returns_is_stored_at_create(self):
        """Submitted UTILITY, accepted as MARKETING — the row must say MARKETING."""
        doc = self._row("gym_create_cat")
        response = {"id": "created_id_1", "status": "PENDING", "category": "MARKETING"}

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request",
            return_value=response,
        ):
            doc.after_insert()

        doc.reload()
        self.assertEqual(doc.category, "MARKETING")
        self.assertEqual(doc.id, "created_id_1")
        self.assertEqual(doc.status, "PENDING")

    def test_a_create_response_without_a_category_leaves_ours_alone(self):
        """It is **not** confirmed that Meta's create response carries `category`. If it
        does not, this write-back is a harmless no-op and the reconcile paths cover it —
        whereas an unconditional `response.get("category")` would replace a plausible
        value with None, which is worse than the drift it was meant to fix."""
        doc = self._row("gym_create_nocat")
        response = {"id": "created_id_2", "status": "PENDING"}

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request",
            return_value=response,
        ):
            doc.after_insert()

        doc.reload()
        self.assertEqual(doc.category, "UTILITY")
        self.assertEqual(doc.id, "created_id_2", "the fields that always worked still do")

    # ---- update -----------------------------------------------------------

    def test_the_update_path_no_longer_discards_its_response(self):
        """An edit can change how Meta reads the template's intent — a body that asks the
        member to renew is how a utility template becomes MARKETING."""
        doc = self._row("gym_update_cat", template_id="updated_id_1")

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request",
            return_value={"success": True, "category": "MARKETING"},
        ):
            doc.update_template()

        self.assertEqual(doc.category, "MARKETING")

    def test_the_update_path_tolerates_a_response_that_is_not_a_dict(self):
        """This path previously ignored its return value entirely, so nothing constrained
        the shape. Reading it must not become a new way for a save to throw."""
        doc = self._row("gym_update_odd", template_id="updated_id_2")

        with patch(
            "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.whatsapp_templates.make_post_request",
            return_value=None,
        ):
            doc.update_template()

        self.assertEqual(doc.category, "UTILITY")
