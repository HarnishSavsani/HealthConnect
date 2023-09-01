# -*- coding: utf-8 -*-
# Copyright (c) 2020, healthconnect Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import healthconnect
from healthconnect import _
from healthconnect.model.document import Document
from healthconnect.utils import cstr

from healthcare.healthcare.doctype.patient_encounter.patient_encounter import (
	get_prescription_dates,
)


class InpatientMedicationOrder(Document):
	def validate(self):
		self.validate_inpatient()
		self.validate_duplicate()
		self.set_total_orders()
		self.set_status()

	def on_submit(self):
		self.validate_inpatient()
		self.set_status()

	def on_cancel(self):
		self.set_status()

	def validate_inpatient(self):
		if not self.inpatient_record:
			healthconnect.throw(_("No Inpatient Record found against patient {0}").format(self.patient))

	def validate_duplicate(self):
		existing_mo = healthconnect.db.exists(
			"Inpatient Medication Order",
			{
				"patient_encounter": self.patient_encounter,
				"docstatus": ("!=", 2),
				"name": ("!=", self.name),
			},
		)
		if existing_mo:
			healthconnect.throw(
				_("An Inpatient Medication Order {0} against Patient Encounter {1} already exists.").format(
					existing_mo, self.patient_encounter
				),
				healthconnect.DuplicateEntryError,
			)

	def set_total_orders(self):
		self.db_set("total_orders", len(self.medication_orders))

	def set_status(self):
		status = {"0": "Draft", "1": "Submitted", "2": "Cancelled"}[cstr(self.docstatus or 0)]

		if self.docstatus == 1:
			if not self.completed_orders:
				status = "Pending"
			elif self.completed_orders < self.total_orders:
				status = "In Process"
			else:
				status = "Completed"

		self.db_set("status", status)

	@healthconnect.whitelist()
	def add_order_entries(self, order):
		if order.get("drug_code"):
			dosage = healthconnect.get_doc("Prescription Dosage", order.get("dosage"))
			dates = get_prescription_dates(order.get("period"), self.start_date)
			for date in dates:
				for dose in dosage.dosage_strength:
					entry = self.append("medication_orders")
					entry.drug = order.get("drug_code")
					entry.drug_name = healthconnect.db.get_value("Item", order.get("drug_code"), "item_name")
					entry.dosage = dose.strength
					entry.dosage_form = order.get("dosage_form")
					entry.date = date
					entry.time = dose.strength_time
			self.end_date = dates[-1]
		return

	@healthconnect.whitelist()
	def get_from_encounter(self, encounter):
		patient_encounter = healthconnect.get_doc("Patient Encounter", encounter)
		if not patient_encounter.drug_prescription:
			return
		for drug in patient_encounter.drug_prescription:
			self.add_order_entries(drug)