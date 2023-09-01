# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

import datetime
import json

import healthconnect
from healthconnect.model.document import Document
from healthconnect.utils import getdate


class FeeValidity(Document):
	def validate(self):
		self.update_status()

	def update_status(self):
		if getdate(self.valid_till) < getdate():
			self.status = "Expired"
		elif self.visited == self.max_visits:
			self.status = "Completed"
		else:
			self.status = "Active"


def create_fee_validity(appointment):
	if patient_has_validity(appointment):
		return

	fee_validity = healthconnect.new_doc("Fee Validity")
	fee_validity.practitioner = appointment.practitioner
	fee_validity.patient = appointment.patient
	fee_validity.medical_department = appointment.department
	fee_validity.patient_appointment = appointment.name
	fee_validity.sales_invoice_ref = healthconnect.db.get_value(
		"Sales Invoice Item", {"reference_dn": appointment.name}, "parent"
	)
	fee_validity.max_visits = healthconnect.db.get_single_value("Healthcare Settings", "max_visits") or 1
	valid_days = healthconnect.db.get_single_value("Healthcare Settings", "valid_days") or 1
	fee_validity.visited = 0
	fee_validity.start_date = getdate(appointment.appointment_date)
	fee_validity.valid_till = getdate(appointment.appointment_date) + datetime.timedelta(
		days=int(valid_days)
	)
	fee_validity.save(ignore_permissions=True)
	return fee_validity


def patient_has_validity(appointment):
	validity_exists = healthconnect.db.exists(
		"Fee Validity",
		{
			"practitioner": appointment.practitioner,
			"patient": appointment.patient,
			"status": "Active",
			"valid_till": [">=", appointment.appointment_date],
			"start_date": ["<=", appointment.appointment_date],
		},
	)

	return validity_exists


@healthconnect.whitelist()
def check_fee_validity(appointment, date=None, practitioner=None):
	if not healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups"):
		return

	if isinstance(appointment, str):
		appointment = json.loads(appointment)
		appointment = healthconnect.get_doc(appointment)

	date = getdate(date) if date else appointment.appointment_date

	filters = {
		"practitioner": practitioner if practitioner else appointment.practitioner,
		"patient": appointment.patient,
		"valid_till": (">=", date),
		"start_date": ("<=", date),
	}
	if appointment.status != "Cancelled":
		filters["status"] = "Active"

	validity = healthconnect.db.exists(
		"Fee Validity",
		filters,
	)

	if not validity:
		# return valid fee validity when rescheduling appointment
		if appointment.get("__islocal"):
			return
		else:
			validity = get_fee_validity(appointment.get("name"), date) or None
			if validity:
				return validity
		return

	validity = healthconnect.get_doc("Fee Validity", validity)
	return validity


def manage_fee_validity(appointment):
	free_follow_ups = healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups")
	# Update fee validity dates when rescheduling an invoiced appointment
	if free_follow_ups:
		invoiced_fee_validity = healthconnect.db.exists(
			"Fee Validity", {"patient_appointment": appointment.name}
		)
		if invoiced_fee_validity and appointment.invoiced:
			start_date = healthconnect.db.get_value("Fee Validity", invoiced_fee_validity, "start_date")
			if getdate(appointment.appointment_date) != start_date:
				healthconnect.db.set_value(
					"Fee Validity",
					invoiced_fee_validity,
					{
						"start_date": appointment.appointment_date,
						"valid_till": getdate(appointment.appointment_date)
						+ datetime.timedelta(
							days=int(healthconnect.db.get_single_value("Healthcare Settings", "valid_days") or 1)
						),
					},
				)

	fee_validity = check_fee_validity(appointment)

	if fee_validity:
		exists = healthconnect.db.exists("Fee Validity Reference", {"appointment": appointment.name})
		if appointment.status == "Cancelled" and fee_validity.visited > 0:
			fee_validity.visited -= 1
			healthconnect.db.delete("Fee Validity Reference", {"appointment": appointment.name})
		elif fee_validity.status != "Active":
			return
		elif appointment.name != fee_validity.patient_appointment and not exists:
			fee_validity.visited += 1
			fee_validity.append("ref_appointments", {"appointment": appointment.name})
		fee_validity.save(ignore_permissions=True)
	else:
		# remove appointment from fee validity reference when rescheduling an appointment to date not in fee validity
		free_visit_validity = healthconnect.db.get_value(
			"Fee Validity Reference", {"appointment": appointment.name}, "parent"
		)
		if free_visit_validity:
			fee_validity = healthconnect.get_doc(
				"Fee Validity",
				free_visit_validity,
			)
			if fee_validity:
				healthconnect.db.delete("Fee Validity Reference", {"appointment": appointment.name})
				if fee_validity.visited > 0:
					fee_validity.visited -= 1
					fee_validity.save(ignore_permissions=True)
		fee_validity = create_fee_validity(appointment)
	return fee_validity


@healthconnect.whitelist()
def get_fee_validity(appointment_name, date):
	"""
	Get the fee validity details for the free visit appointment
	:params appointment_name: Appointment doc name
	:params date: Schedule date
	:return fee validity name and valid_till values of free visit appointments
	"""
	if appointment_name:
		appointment_doc = healthconnect.get_doc("Patient Appointment", appointment_name)
	fee_validity = healthconnect.qb.DocType("Fee Validity")
	child = healthconnect.qb.DocType("Fee Validity Reference")

	return (
		healthconnect.qb.from_(fee_validity)
		.inner_join(child)
		.on(fee_validity.name == child.parent)
		.select(fee_validity.name, fee_validity.valid_till)
		.where(fee_validity.status == "Active")
		.where(fee_validity.start_date <= date)
		.where(fee_validity.valid_till >= date)
		.where(fee_validity.patient == appointment_doc.patient)
		.where(fee_validity.practitioner == appointment_doc.practitioner)
		.where(child.appointment == appointment_name)
	).run(as_dict=True)


def update_validity_status():
	# update the status of fee validity daily
	validities = healthconnect.db.get_all("Fee Validity", {"status": ["not in", ["Expired", "Cancelled"]]})

	for fee_validity in validities:
		fee_validity_doc = healthconnect.get_doc("Fee Validity", fee_validity.name)
		fee_validity_doc.update_status()
		fee_validity_doc.save()
