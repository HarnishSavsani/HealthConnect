# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt


import healthconnect
from erpnext.accounts.doctype.pos_profile.test_pos_profile import make_pos_profile
from healthconnect.tests.utils import healthconnectTestCase
from healthconnect.utils import add_days, nowdate

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment,
	create_healthcare_docs,
	create_healthcare_service_items,
	update_status,
)

test_dependencies = ["Company"]


class TestFeeValidity(healthconnectTestCase):
	def setUp(self):
		healthconnect.db.sql("""delete from `tabPatient Appointment`""")
		healthconnect.db.sql("""delete from `tabFee Validity`""")
		healthconnect.db.sql("""delete from `tabPatient`""")
		make_pos_profile()

	def test_fee_validity(self):
		item = create_healthcare_service_items()
		healthcare_settings = healthconnect.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.max_visits = 1
		healthcare_settings.valid_days = 7
		healthcare_settings.automate_appointment_invoicing = 1
		healthcare_settings.op_consulting_charge_item = item
		healthcare_settings.save(ignore_permissions=True)
		patient, practitioner = create_healthcare_docs()

		# For first appointment, invoice is generated. First appointment not considered in fee validity
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = healthconnect.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		invoiced = healthconnect.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)
		self.assertTrue(fee_validity)
		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should not be invoiced as it is within fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 4))
		invoiced = healthconnect.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 0)

		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "visited"), 1)
		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "status"), "Completed")

		# appointment should be invoiced as it is within fee validity but the max_visits are exceeded, should insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 5), invoice=1)
		invoiced = healthconnect.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = healthconnect.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should be invoiced as it is not within fee validity and insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 13), invoice=1)
		invoiced = healthconnect.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = healthconnect.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# For first appointment cancel should cancel fee validity
		update_status(appointment.name, "Cancelled")
		self.assertEqual(healthconnect.db.get_value("Fee Validity", fee_validity, "status"), "Cancelled")
