# -*- coding: utf-8 -*-
# Copyright (c) 2020, healthconnect Technologies Pvt. Ltd. and Contributors
# See license.txt


import json

import healthconnect
from healthconnect.tests.utils import healthconnectTestCase
from healthconnect.utils import getdate, strip_html

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_patient,
)


class TestPatientHistorySettings(healthconnectTestCase):
	def setUp(self):
		dt = create_custom_doctype()
		settings = healthconnect.get_single("Patient History Settings")
		settings.append(
			"custom_doctypes",
			{
				"document_type": dt.name,
				"date_fieldname": "date",
				"selected_fields": json.dumps(
					[
						{"label": "Date", "fieldname": "date", "fieldtype": "Date"},
						{"label": "Rating", "fieldname": "rating", "fieldtype": "Rating"},
						{"label": "Feedback", "fieldname": "feedback", "fieldtype": "Small Text"},
					]
				),
			},
		)
		settings.save()

	def test_custom_doctype_medical_record(self):
		# tests for medical record creation of standard doctypes in test_patient_medical_record.py
		patient = create_patient()
		doc = create_doc(patient)
		# check for medical record
		medical_rec = healthconnect.db.exists(
			"Patient Medical Record", {"status": "Open", "reference_name": doc.name}
		)
		self.assertTrue(medical_rec)

		medical_rec = healthconnect.get_doc("Patient Medical Record", medical_rec)
		expected_subject = "Date:{0}Rating:3Feedback:Test Patient History Settings".format(
			healthconnect.utils.format_date(getdate())
		)
		self.assertEqual(strip_html(medical_rec.subject), expected_subject)
		self.assertEqual(medical_rec.patient, patient)
		self.assertEqual(medical_rec.communication_date, getdate())


def create_custom_doctype():
	if not healthconnect.db.exists("DocType", "Test Patient Feedback"):
		doc = healthconnect.get_doc(
			{
				"doctype": "DocType",
				"module": "Healthcare",
				"custom": 1,
				"is_submittable": 1,
				"fields": [
					{"label": "Date", "fieldname": "date", "fieldtype": "Date"},
					{"label": "Patient", "fieldname": "patient", "fieldtype": "Link", "options": "Patient"},
					{"label": "Rating", "fieldname": "rating", "fieldtype": "Rating"},
					{"label": "Feedback", "fieldname": "feedback", "fieldtype": "Small Text"},
				],
				"permissions": [{"role": "System Manager", "read": 1}],
				"name": "Test Patient Feedback",
			}
		)
		doc.insert()
		return doc
	else:
		return healthconnect.get_doc("DocType", "Test Patient Feedback")


def create_doc(patient):
	doc = healthconnect.get_doc(
		{
			"doctype": "Test Patient Feedback",
			"patient": patient,
			"date": getdate(),
			"rating": 3,
			"feedback": "Test Patient History Settings",
		}
	).insert()
	doc.submit()

	return doc
