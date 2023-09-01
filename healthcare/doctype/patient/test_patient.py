# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt


import os

import healthconnect
from healthconnect.tests.utils import healthconnectTestCase

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_patient,
)


class TestPatient(healthconnectTestCase):
	def test_customer_created(self):
		healthconnect.db.sql("""delete from `tabPatient`""")
		healthconnect.db.set_value("Healthcare Settings", None, "link_customer_to_patient", 1)
		patient = create_patient()
		self.assertTrue(healthconnect.db.get_value("Patient", patient, "customer"))

	def test_patient_registration(self):
		healthconnect.db.sql("""delete from `tabPatient`""")
		settings = healthconnect.get_single("Healthcare Settings")
		settings.collect_registration_fee = 1
		settings.registration_fee = 500
		settings.save()

		patient = create_patient()
		patient = healthconnect.get_doc("Patient", patient)
		self.assertEqual(patient.status, "Disabled")

		# check sales invoice and patient status
		result = patient.invoice_patient_registration()
		self.assertTrue(healthconnect.db.exists("Sales Invoice", result.get("invoice")))
		self.assertTrue(patient.status, "Active")

		settings.collect_registration_fee = 0
		settings.save()

	def test_patient_contact(self):
		healthconnect.db.sql("""delete from `tabPatient` where name like '_Test Patient%'""")
		healthconnect.db.sql("""delete from `tabCustomer` where name like '_Test Patient%'""")
		healthconnect.db.sql("""delete from `tabContact` where name like'_Test Patient%'""")
		healthconnect.db.sql("""delete from `tabDynamic Link` where parent like '_Test Patient%'""")

		patient = create_patient(
			patient_name="_Test Patient Contact", email="test-patient@example.com", mobile="+91 0000000001"
		)
		customer = healthconnect.db.get_value("Patient", patient, "customer")
		self.assertTrue(customer)
		self.assertTrue(
			healthconnect.db.exists(
				"Dynamic Link", {"parenttype": "Contact", "link_doctype": "Patient", "link_name": patient}
			)
		)
		self.assertTrue(
			healthconnect.db.exists(
				"Dynamic Link", {"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer}
			)
		)

		# a second patient linking with same customer
		new_patient = create_patient(
			email="test-patient@example.com", mobile="+91 0000000009", customer=customer
		)
		self.assertTrue(
			healthconnect.db.exists(
				"Dynamic Link", {"parenttype": "Contact", "link_doctype": "Patient", "link_name": new_patient}
			)
		)
		self.assertTrue(
			healthconnect.db.exists(
				"Dynamic Link", {"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer}
			)
		)

	def test_patient_user(self):
		healthconnect.db.sql("""delete from `tabUser` where email='test-patient-user@example.com'""")
		healthconnect.db.sql("""delete from `tabDynamic Link` where parent like '_Test Patient%'""")
		healthconnect.db.sql("""delete from `tabPatient` where name like '_Test Patient%'""")

		patient = create_patient(
			patient_name="_Test Patient User",
			email="test-patient-user@example.com",
			mobile="+91 0000000009",
			create_user=True,
		)
		user = healthconnect.db.get_value("Patient", patient, "user_id")
		self.assertTrue(healthconnect.db.exists("User", user))

		new_patient = healthconnect.get_doc(
			{
				"doctype": "Patient",
				"first_name": "_Test Patient Duplicate User",
				"sex": "Male",
				"email": "test-patient-user@example.com",
				"mobile": "+91 0000000009",
				"invite_user": 1,
			}
		)

		self.assertRaises(healthconnect.exceptions.DuplicateEntryError, new_patient.insert)

	def test_patient_image_update_should_update_customer_image(self):
		settings = healthconnect.get_single("Healthcare Settings")
		settings.link_customer_to_patient = 1
		settings.save()

		patient_name = create_patient()
		patient = healthconnect.get_doc("Patient", patient_name)
		patient.image = os.path.abspath("assets/healthconnect/images/default-avatar.png")
		patient.save()

		customer = healthconnect.get_doc("Customer", patient.customer)
		self.assertEqual(customer.image, patient.image)
