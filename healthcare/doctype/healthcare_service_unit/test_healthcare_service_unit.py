# -*- coding: utf-8 -*-
# Copyright (c) 2018, healthconnect Technologies Pvt. Ltd. and Contributors
# See license.txt
import healthconnect
from healthconnect.tests.utils import healthconnectTestCase


class TestHealthcareServiceUnit(healthconnectTestCase):
	def test_create_company_should_create_root_service_unit(self):
		company = healthconnect.get_doc(
			{
				"doctype": "Company",
				"company_name": "Test Hospital",
				"country": "India",
				"default_currency": "INR",
			}
		)
		try:
			company = company.insert()
		except healthconnect.exceptions.DuplicateEntryError:
			pass
		filters = {"company": company.name, "parent_healthcare_service_unit": None}
		root_service_unit = healthconnect.db.exists("Healthcare Service Unit", filters)
		self.assertTrue(root_service_unit)
