# -*- coding: utf-8 -*-
# Copyright (c) 2018, healthconnect Technologies Pvt. Ltd. and Contributors
# See license.txt


import healthconnect
from healthconnect.tests.utils import healthconnectTestCase
from healthconnect.utils import now_datetime, today
from healthconnect.utils.make_random import get_random

from healthcare.healthcare.doctype.inpatient_record.inpatient_record import (
	admit_patient,
	discharge_patient,
	schedule_discharge,
)
from healthcare.healthcare.doctype.lab_test.test_lab_test import create_patient_encounter
from healthcare.healthcare.utils import get_encounters_to_invoice


class TestInpatientRecord(healthconnectTestCase):
	def test_admit_and_discharge(self):
		healthconnect.db.sql("""delete from `tabInpatient Record`""")
		patient = create_patient()
		# Schedule Admission
		ip_record = create_inpatient(patient)
		ip_record.expected_length_of_stay = 0
		ip_record.save(ignore_permissions=True)
		self.assertEqual(ip_record.name, healthconnect.db.get_value("Patient", patient, "inpatient_record"))
		self.assertEqual(ip_record.status, healthconnect.db.get_value("Patient", patient, "inpatient_status"))

		# Admit
		service_unit = get_healthcare_service_unit()
		admit_patient(ip_record, service_unit, now_datetime())
		self.assertEqual("Admitted", healthconnect.db.get_value("Patient", patient, "inpatient_status"))
		self.assertEqual(
			"Occupied", healthconnect.db.get_value("Healthcare Service Unit", service_unit, "occupancy_status")
		)

		# Discharge
		schedule_discharge(healthconnect.as_json({"patient": patient}))
		self.assertEqual(
			"Vacant", healthconnect.db.get_value("Healthcare Service Unit", service_unit, "occupancy_status")
		)

		ip_record1 = healthconnect.get_doc("Inpatient Record", ip_record.name)
		# Validate Pending Invoices
		self.assertRaises(healthconnect.ValidationError, ip_record.discharge)
		mark_invoiced_inpatient_occupancy(ip_record1)

		discharge_patient(ip_record1)

		self.assertEqual(None, healthconnect.db.get_value("Patient", patient, "inpatient_record"))
		self.assertEqual(None, healthconnect.db.get_value("Patient", patient, "inpatient_status"))

	def test_allow_discharge_despite_unbilled_services(self):
		healthconnect.db.sql("""delete from `tabInpatient Record`""")
		setup_inpatient_settings(key="allow_discharge_despite_unbilled_services", value=1)
		patient = create_patient()
		# Schedule Admission
		ip_record = create_inpatient(patient)
		ip_record.expected_length_of_stay = 0
		ip_record.save(ignore_permissions=True)

		# Admit
		service_unit = get_healthcare_service_unit()
		admit_patient(ip_record, service_unit, now_datetime())

		# Discharge
		schedule_discharge(healthconnect.as_json({"patient": patient}))
		self.assertEqual(
			"Vacant", healthconnect.db.get_value("Healthcare Service Unit", service_unit, "occupancy_status")
		)

		ip_record = healthconnect.get_doc("Inpatient Record", ip_record.name)
		# Should not validate Pending Invoices
		ip_record.discharge()

		self.assertEqual(None, healthconnect.db.get_value("Patient", patient, "inpatient_record"))
		self.assertEqual(None, healthconnect.db.get_value("Patient", patient, "inpatient_status"))

		setup_inpatient_settings(key="allow_discharge_despite_unbilled_services", value=0)

	def test_do_not_bill_patient_encounters_for_inpatients(self):
		healthconnect.db.sql("""delete from `tabInpatient Record`""")
		setup_inpatient_settings(key="do_not_bill_inpatient_encounters", value=1)
		patient = create_patient()
		# Schedule Admission
		ip_record = create_inpatient(patient)
		ip_record.expected_length_of_stay = 0
		ip_record.save(ignore_permissions=True)

		# Admit
		service_unit = get_healthcare_service_unit()
		admit_patient(ip_record, service_unit, now_datetime())

		# Patient Encounter
		patient_encounter = create_patient_encounter()
		encounters = get_encounters_to_invoice(patient, "_Test Company")
		encounter_ids = [entry.reference_name for entry in encounters]
		self.assertFalse(patient_encounter.name in encounter_ids)

		# Discharge
		schedule_discharge(healthconnect.as_json({"patient": patient}))
		self.assertEqual(
			"Vacant", healthconnect.db.get_value("Healthcare Service Unit", service_unit, "occupancy_status")
		)

		ip_record = healthconnect.get_doc("Inpatient Record", ip_record.name)
		mark_invoiced_inpatient_occupancy(ip_record)
		discharge_patient(ip_record)
		setup_inpatient_settings(key="do_not_bill_inpatient_encounters", value=0)

	def test_validate_overlap_admission(self):
		healthconnect.db.sql("""delete from `tabInpatient Record`""")
		patient = create_patient()

		ip_record = create_inpatient(patient)
		ip_record.expected_length_of_stay = 0
		ip_record.save(ignore_permissions=True)
		ip_record_new = create_inpatient(patient)
		ip_record_new.expected_length_of_stay = 0
		self.assertRaises(healthconnect.ValidationError, ip_record_new.save)

		service_unit = get_healthcare_service_unit()
		admit_patient(ip_record, service_unit, now_datetime())
		ip_record_new = create_inpatient(patient)
		self.assertRaises(healthconnect.ValidationError, ip_record_new.save)
		healthconnect.db.sql("""delete from `tabInpatient Record`""")


def mark_invoiced_inpatient_occupancy(ip_record):
	if ip_record.inpatient_occupancies:
		for inpatient_occupancy in ip_record.inpatient_occupancies:
			inpatient_occupancy.invoiced = 1
		ip_record.save(ignore_permissions=True)


def setup_inpatient_settings(key, value):
	settings = healthconnect.get_single("Healthcare Settings")
	settings.set(key, value)
	settings.save()


def create_inpatient(patient):
	patient_obj = healthconnect.get_doc("Patient", patient)
	inpatient_record = healthconnect.new_doc("Inpatient Record")
	inpatient_record.patient = patient
	inpatient_record.patient_name = patient_obj.patient_name
	inpatient_record.gender = patient_obj.sex
	inpatient_record.blood_group = patient_obj.blood_group
	inpatient_record.dob = patient_obj.dob
	inpatient_record.mobile = patient_obj.mobile
	inpatient_record.email = patient_obj.email
	inpatient_record.phone = patient_obj.phone
	inpatient_record.inpatient = "Scheduled"
	inpatient_record.scheduled_date = today()
	inpatient_record.company = "_Test Company"
	return inpatient_record


def get_healthcare_service_unit(unit_name=None):
	if not unit_name:
		service_unit = get_random(
			"Healthcare Service Unit", filters={"inpatient_occupancy": 1, "company": "_Test Company"}
		)
	else:
		service_unit = healthconnect.db.exists(
			"Healthcare Service Unit", {"healthcare_service_unit_name": unit_name}
		)

	if not service_unit:
		service_unit = healthconnect.new_doc("Healthcare Service Unit")
		service_unit.healthcare_service_unit_name = unit_name or "_Test Service Unit Ip Occupancy"
		service_unit.company = "_Test Company"
		service_unit.service_unit_type = get_service_unit_type()
		service_unit.inpatient_occupancy = 1
		service_unit.occupancy_status = "Vacant"
		service_unit.is_group = 0
		service_unit_parent_name = healthconnect.db.exists(
			{
				"doctype": "Healthcare Service Unit",
				"healthcare_service_unit_name": "_Test All Healthcare Service Units",
				"is_group": 1,
			}
		)
		if not service_unit_parent_name:
			parent_service_unit = healthconnect.new_doc("Healthcare Service Unit")
			parent_service_unit.healthcare_service_unit_name = "_Test All Healthcare Service Units"
			parent_service_unit.is_group = 1
			parent_service_unit.save(ignore_permissions=True)
			service_unit.parent_healthcare_service_unit = parent_service_unit.name
		else:
			service_unit.parent_healthcare_service_unit = service_unit_parent_name
		service_unit.save(ignore_permissions=True)
		return service_unit.name
	return service_unit


def get_service_unit_type():
	service_unit_type = get_random("Healthcare Service Unit Type", filters={"inpatient_occupancy": 1})

	if not service_unit_type:
		service_unit_type = healthconnect.new_doc("Healthcare Service Unit Type")
		service_unit_type.service_unit_type = "_Test Service Unit Type Ip Occupancy"
		service_unit_type.inpatient_occupancy = 1
		service_unit_type.save(ignore_permissions=True)
		return service_unit_type.name
	return service_unit_type


def create_patient():
	patient = healthconnect.db.exists("Patient", "_Test IPD Patient")
	if not patient:
		patient = healthconnect.new_doc("Patient")
		patient.first_name = "_Test IPD Patient"
		patient.sex = "Female"
		patient.save(ignore_permissions=True)
		patient = patient.name
	return patient
