# Copyright (c) 2025, Shridhar Patil and Contributors
# See license.txt

import frappe
from frappe_whatsapp.testing import IntegrationTestCase

from frappe_whatsapp.frappe_whatsapp.report.bulk_whatsapp_status.bulk_whatsapp_status import (
    execute,
    get_columns,
    get_data,
)


class TestBulkWhatsAppStatusReport(IntegrationTestCase):
    """Tests for Bulk WhatsApp Status report."""

    def test_get_columns(self):
        """Test get_columns returns expected columns."""
        columns = get_columns()
        self.assertIsInstance(columns, list)
        self.assertTrue(len(columns) > 0)

        field_names = [col["fieldname"] for col in columns]
        self.assertIn("name", field_names)
        self.assertIn("title", field_names)
        self.assertIn("recipient_count", field_names)
        self.assertIn("sent_count", field_names)
        self.assertIn("delivered_count", field_names)
        self.assertIn("read_count", field_names)
        self.assertIn("failed_count", field_names)
        self.assertIn("status", field_names)

    def test_execute_returns_columns_and_data(self):
        """Test execute returns tuple of columns and data."""
        columns, data = execute()
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)

    def test_execute_with_filters(self):
        """Test execute with date filters."""
        columns, data = execute(filters={
            "from_date": "2024-01-01",
            "to_date": "2099-12-31",
        })
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)

    def test_execute_with_status_filter(self):
        """Test execute with status filter."""
        columns, data = execute(filters={"status": "Completed"})
        self.assertIsInstance(data, list)

    def test_get_data_empty_filters(self):
        """Test get_data with empty filters returns list."""
        data = get_data({})
        self.assertIsInstance(data, list)
