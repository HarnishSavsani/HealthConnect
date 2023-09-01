# -*- coding: utf-8 -*-
# Copyright (c) 2018, healthconnect Technologies Pvt. Ltd. and Contributors
# See license.txt


import healthconnect
from healthconnect.tests.utils import healthconnectTestCase

from healthcare.healthcare.doctype.patient_encounter.patient_encounter import PatientEncounter


class TestPatientEncounter(healthconnectTestCase):
	def setUp(self):
		try:
			gender_m = healthconnect.get_doc({"doctype": "Gender", "gender": "MALE"}).insert()
			gender_f = healthconnect.get_doc({"doctype": "Gender", "gender": "FEMALE"}).insert()
		except healthconnect.exceptions.DuplicateEntryError:
			gender_m = healthconnect.get_doc({"doctype": "Gender", "gender": "MALE"})
			gender_f = healthconnect.get_doc({"doctype": "Gender", "gender": "FEMALE"})

		self.patient_male = healthconnect.get_doc(
			{
				"doctype": "Patient",
				"first_name": "John",
				"sex": gender_m.gender,
			}
		).insert()
		self.patient_female = healthconnect.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Curie",
				"sex": gender_f.gender,
			}
		).insert()
		self.practitioner = healthconnect.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Doc",
				"sex": "MALE",
			}
		).insert()
		try:
			self.care_plan_male = healthconnect.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			).insert()
			self.care_plan_female = healthconnect.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			).insert()
		except healthconnect.exceptions.DuplicateEntryError:
			self.care_plan_male = healthconnect.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			)
			self.care_plan_female = healthconnect.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			)

	def test_treatment_plan_template_filter(self):
		encounter = healthconnect.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_male.name,
				"practitioner": self.practitioner.name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_male.template_name)

		encounter = healthconnect.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_female.name,
				"practitioner": self.practitioner.name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_female.template_name)
