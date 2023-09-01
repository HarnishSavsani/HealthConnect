# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt


import datetime
import json

import healthconnect
from erpnext.setup.doctype.employee.employee import is_holiday
from healthconnect import _
from healthconnect.core.doctype.sms_settings.sms_settings import send_sms
from healthconnect.model.document import Document
from healthconnect.model.mapper import get_mapped_doc
from healthconnect.utils import flt, format_date, get_link_to_form, get_time, getdate

from healthcare.healthcare.doctype.fee_validity.fee_validity import (
	check_fee_validity,
	get_fee_validity,
	manage_fee_validity,
)
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)
from healthcare.healthcare.utils import get_appointment_billing_item_and_rate


class MaximumCapacityError(healthconnect.ValidationError):
	pass


class OverlapError(healthconnect.ValidationError):
	pass


class PatientAppointment(Document):
	def validate(self):
		self.validate_overlaps()
		self.validate_based_on_appointments_for()
		self.validate_service_unit()
		self.set_appointment_datetime()
		self.validate_customer_created()
		self.set_status()
		self.set_title()
		self.update_event()
		self.set_postition_in_queue()

	def on_update(self):
		invoice_appointment(self)
		self.update_fee_validity()

	def after_insert(self):
		self.update_prescription_details()
		self.set_payment_details()
		send_confirmation_msg(self)
		self.insert_calendar_event()

	def set_title(self):
		if self.practitioner:
			self.title = _("{0} with {1}").format(
				self.patient_name or self.patient, self.practitioner_name or self.practitioner
			)
		else:
			self.title = _("{0} at {1}").format(
				self.patient_name or self.patient, self.get(healthconnect.scrub(self.appointment_for))
			)

	def set_status(self):
		today = getdate()
		appointment_date = getdate(self.appointment_date)

		# If appointment is created for today set status as Open else Scheduled
		if appointment_date == today:
			if self.status not in ["Checked In", "Checked Out"]:
				self.status = "Open"

		elif appointment_date > today:
			self.status = "Scheduled"

		elif appointment_date < today:
			if self.status == "Scheduled":
				self.status = "No Show"

	def validate_overlaps(self):
		if self.appointment_based_on_check_in:
			if healthconnect.db.exists(
				{
					"doctype": "Patient Appointment",
					"patient": self.patient,
					"appointment_date": self.appointment_date,
					"appointment_time": self.appointment_time,
					"appointment_based_on_check_in": True,
					"name": ["!=", self.name],
				}
			):
				healthconnect.throw(_("Patient already has an appointment booked for the same day!"), OverlapError)
			return

		if not self.practitioner:
			return

		end_time = datetime.datetime.combine(
			getdate(self.appointment_date), get_time(self.appointment_time)
		) + datetime.timedelta(minutes=flt(self.duration))

		# all appointments for both patient and practitioner overlapping the duration of this appointment
		overlapping_appointments = healthconnect.db.sql(
			"""
			SELECT
				name, practitioner, patient, appointment_time, duration, service_unit
			FROM
				`tabPatient Appointment`
			WHERE
				appointment_date=%(appointment_date)s AND name!=%(name)s AND status NOT IN ("Closed", "Cancelled") AND
				(practitioner=%(practitioner)s OR patient=%(patient)s) AND
				((appointment_time<%(appointment_time)s AND appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) OR
				(appointment_time>%(appointment_time)s AND appointment_time<%(end_time)s) OR
				(appointment_time=%(appointment_time)s))
			""",
			{
				"appointment_date": self.appointment_date,
				"name": self.name,
				"practitioner": self.practitioner,
				"patient": self.patient,
				"appointment_time": self.appointment_time,
				"end_time": end_time.time(),
			},
			as_dict=True,
		)

		if not overlapping_appointments:
			return  # No overlaps, nothing to validate!

		if self.service_unit:  # validate service unit capacity if overlap enabled
			allow_overlap, service_unit_capacity = healthconnect.get_value(
				"Healthcare Service Unit", self.service_unit, ["overlap_appointments", "service_unit_capacity"]
			)
			if allow_overlap:
				service_unit_appointments = list(
					filter(
						lambda appointment: appointment["service_unit"] == self.service_unit
						and appointment["patient"] != self.patient,
						overlapping_appointments,
					)
				)  # if same patient already booked, it should be an overlap
				if len(service_unit_appointments) >= (service_unit_capacity or 1):
					healthconnect.throw(
						_("Not allowed, {} cannot exceed maximum capacity {}").format(
							healthconnect.bold(self.service_unit), healthconnect.bold(service_unit_capacity or 1)
						),
						MaximumCapacityError,
					)
				else:  # service_unit_appointments within capacity, remove from overlapping_appointments
					overlapping_appointments = [
						appointment
						for appointment in overlapping_appointments
						if appointment not in service_unit_appointments
					]

		if overlapping_appointments:
			healthconnect.throw(
				_("Not allowed, cannot overlap appointment {}").format(
					healthconnect.bold(", ".join([appointment["name"] for appointment in overlapping_appointments]))
				),
				OverlapError,
			)

	def validate_based_on_appointments_for(self):
		if self.appointment_for:
			# fieldname: practitioner / department / service_unit
			appointment_for_field = healthconnect.scrub(self.appointment_for)

			# validate if respective field is set
			if not self.get(appointment_for_field):
				healthconnect.throw(
					_("Please enter {}").format(healthconnect.bold(self.appointment_for)),
					healthconnect.MandatoryError,
				)

			if self.appointment_for == "Practitioner":
				# appointments for practitioner are validated separately,
				# based on practitioner schedule
				return

			# validate if patient already has an appointment for the day
			booked_appointment = healthconnect.db.exists(
				"Patient Appointment",
				{
					"patient": self.patient,
					"status": ["!=", "Cancelled"],
					appointment_for_field: self.get(appointment_for_field),
					"appointment_date": self.appointment_date,
					"name": ["!=", self.name],
				},
			)

			if booked_appointment:
				healthconnect.throw(
					_("Patient already has an appointment {} booked for {} on {}").format(
						get_link_to_form("Patient Appointment", booked_appointment),
						healthconnect.bold(self.get(appointment_for_field)),
						healthconnect.bold(format_date(self.appointment_date)),
					),
					healthconnect.DuplicateEntryError,
				)

	def validate_service_unit(self):
		if self.inpatient_record and self.service_unit:
			from healthcare.healthcare.doctype.inpatient_medication_entry.inpatient_medication_entry import (
				get_current_healthcare_service_unit,
			)

			is_inpatient_occupancy_unit = healthconnect.db.get_value(
				"Healthcare Service Unit", self.service_unit, "inpatient_occupancy"
			)
			service_unit = get_current_healthcare_service_unit(self.inpatient_record)
			if is_inpatient_occupancy_unit and service_unit != self.service_unit:
				msg = (
					_("Patient {0} is not admitted in the service unit {1}").format(
						healthconnect.bold(self.patient), healthconnect.bold(self.service_unit)
					)
					+ "<br>"
				)
				msg += _(
					"Appointment for service units with Inpatient Occupancy can only be created against the unit where patient has been admitted."
				)
				healthconnect.throw(msg, title=_("Invalid Healthcare Service Unit"))

	def set_appointment_datetime(self):
		self.appointment_datetime = "%s %s" % (
			self.appointment_date,
			self.appointment_time or "00:00:00",
		)

	def set_payment_details(self):
		if healthconnect.db.get_single_value("Healthcare Settings", "automate_appointment_invoicing"):
			details = get_appointment_billing_item_and_rate(self)
			self.db_set("billing_item", details.get("service_item"))
			if not self.paid_amount:
				self.db_set("paid_amount", details.get("practitioner_charge"))

	def validate_customer_created(self):
		if healthconnect.db.get_single_value("Healthcare Settings", "automate_appointment_invoicing"):
			if not healthconnect.db.get_value("Patient", self.patient, "customer"):
				msg = _("Please set a Customer linked to the Patient")
				msg += " <b><a href='/app/Form/Patient/{0}'>{0}</a></b>".format(self.patient)
				healthconnect.throw(msg, title=_("Customer Not Found"))

	def update_prescription_details(self):
		if self.procedure_prescription:
			healthconnect.db.set_value(
				"Procedure Prescription", self.procedure_prescription, "appointment_booked", 1
			)
			if self.procedure_template:
				comments = healthconnect.db.get_value(
					"Procedure Prescription", self.procedure_prescription, "comments"
				)
				if comments:
					healthconnect.db.set_value("Patient Appointment", self.name, "notes", comments)

	def update_fee_validity(self):
		if (
			not healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups")
			or not self.practitioner
		):
			return

		fee_validity = manage_fee_validity(self)
		if fee_validity:
			healthconnect.msgprint(
				_("{0} has fee validity till {1}").format(
					healthconnect.bold(self.patient_name), format_date(fee_validity.valid_till)
				)
			)

	def insert_calendar_event(self):
		if not self.practitioner:
			return

		starts_on = datetime.datetime.combine(
			getdate(self.appointment_date), get_time(self.appointment_time)
		)
		ends_on = starts_on + datetime.timedelta(minutes=flt(self.duration))
		google_calendar = healthconnect.db.get_value(
			"Healthcare Practitioner", self.practitioner, "google_calendar"
		)
		if not google_calendar:
			google_calendar = healthconnect.db.get_single_value("Healthcare Settings", "default_google_calendar")

		if self.appointment_type:
			color = healthconnect.db.get_value("Appointment Type", self.appointment_type, "color")
		else:
			color = ""

		event = healthconnect.get_doc(
			{
				"doctype": "Event",
				"subject": f"{self.title} - {self.company}",
				"event_type": "Private",
				"color": color,
				"send_reminder": 1,
				"starts_on": starts_on,
				"ends_on": ends_on,
				"status": "Open",
				"all_day": 0,
				"sync_with_google_calendar": 1 if self.add_video_conferencing and google_calendar else 0,
				"add_video_conferencing": 1 if self.add_video_conferencing and google_calendar else 0,
				"google_calendar": google_calendar,
				"description": f"{self.title} - {self.company}",
				"pulled_from_google_calendar": 0,
			}
		)
		participants = []

		participants.append(
			{"reference_doctype": "Healthcare Practitioner", "reference_docname": self.practitioner}
		)
		participants.append({"reference_doctype": "Patient", "reference_docname": self.patient})

		event.update({"event_participants": participants})

		event.insert(ignore_permissions=True)

		event.reload()
		if self.add_video_conferencing and not event.google_meet_link:
			healthconnect.msgprint(
				_("Could not add conferencing to this Appointment, please contact System Manager"),
				indicator="error",
				alert=True,
			)

		self.db_set({"event": event.name, "google_meet_link": event.google_meet_link})
		self.notify_update()

	@healthconnect.whitelist()
	def get_therapy_types(self):
		if not self.therapy_plan:
			return

		therapy_types = []
		doc = healthconnect.get_doc("Therapy Plan", self.therapy_plan)
		for entry in doc.therapy_plan_details:
			therapy_types.append(entry.therapy_type)

		return therapy_types

	def update_event(self):
		if self.event:
			event_doc = healthconnect.get_doc("Event", self.event)
			starts_on = datetime.datetime.combine(
				getdate(self.appointment_date), get_time(self.appointment_time)
			)
			ends_on = starts_on + datetime.timedelta(minutes=flt(self.duration))
			if (
				starts_on != event_doc.starts_on
				or self.add_video_conferencing != event_doc.add_video_conferencing
			):
				event_doc.starts_on = starts_on
				event_doc.ends_on = ends_on
				event_doc.add_video_conferencing = self.add_video_conferencing
				event_doc.save()
				event_doc.reload()
				self.google_meet_link = event_doc.google_meet_link

	def set_postition_in_queue(self):
		if self.status == "Checked In" and not self.position_in_queue:
			app_count = healthconnect.db.count(
				"Patient Appointment",
				{
					"status": "Checked In",
					"practitioner": self.practitioner,
					"service_unit": self.service_unit,
					"appointment_time": self.appointment_time,
				},
			)
			self.position_in_queue = app_count + 1


@healthconnect.whitelist()
def check_payment_fields_reqd(patient):
	automate_invoicing = healthconnect.db.get_single_value(
		"Healthcare Settings", "automate_appointment_invoicing"
	)
	free_follow_ups = healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups")
	if automate_invoicing:
		if free_follow_ups:
			fee_validity = healthconnect.db.exists("Fee Validity", {"patient": patient, "status": "Active"})
			if fee_validity:
				return {"fee_validity": fee_validity}
		return True
	return False


def invoice_appointment(appointment_doc):
	automate_invoicing = healthconnect.db.get_single_value(
		"Healthcare Settings", "automate_appointment_invoicing"
	)
	appointment_invoiced = healthconnect.db.get_value(
		"Patient Appointment", appointment_doc.name, "invoiced"
	)
	enable_free_follow_ups = healthconnect.db.get_single_value(
		"Healthcare Settings", "enable_free_follow_ups"
	)
	if enable_free_follow_ups:
		fee_validity = check_fee_validity(appointment_doc)

		if fee_validity and fee_validity.status != "Active":
			fee_validity = None
		elif not fee_validity:
			if get_fee_validity(appointment_doc.name, appointment_doc.appointment_date):
				return
	else:
		fee_validity = None

	if automate_invoicing and not appointment_invoiced and not fee_validity:
		create_sales_invoice(appointment_doc)


def create_sales_invoice(appointment_doc):
	sales_invoice = healthconnect.new_doc("Sales Invoice")
	sales_invoice.patient = appointment_doc.patient
	sales_invoice.customer = healthconnect.get_value("Patient", appointment_doc.patient, "customer")
	sales_invoice.appointment = appointment_doc.name
	sales_invoice.due_date = getdate()
	sales_invoice.company = appointment_doc.company
	sales_invoice.debit_to = get_receivable_account(appointment_doc.company)

	item = sales_invoice.append("items", {})
	item = get_appointment_item(appointment_doc, item)

	# Add payments if payment details are supplied else proceed to create invoice as Unpaid
	if appointment_doc.mode_of_payment and appointment_doc.paid_amount:
		sales_invoice.is_pos = 1
		payment = sales_invoice.append("payments", {})
		payment.mode_of_payment = appointment_doc.mode_of_payment
		payment.amount = appointment_doc.paid_amount

	sales_invoice.set_missing_values(for_validate=True)
	sales_invoice.flags.ignore_mandatory = True
	sales_invoice.save(ignore_permissions=True)
	sales_invoice.submit()
	healthconnect.msgprint(_("Sales Invoice {0} created").format(sales_invoice.name), alert=True)
	healthconnect.db.set_value(
		"Patient Appointment",
		appointment_doc.name,
		{"invoiced": 1, "ref_sales_invoice": sales_invoice.name},
	)
	appointment_doc.reload()


def check_is_new_patient(patient, name=None):
	filters = {"patient": patient, "status": ("!=", "Cancelled")}
	if name:
		filters["name"] = ("!=", name)

	has_previous_appointment = healthconnect.db.exists("Patient Appointment", filters)
	return not has_previous_appointment


def get_appointment_item(appointment_doc, item):
	details = get_appointment_billing_item_and_rate(appointment_doc)
	charge = appointment_doc.paid_amount or details.get("practitioner_charge")
	item.item_code = details.get("service_item")
	item.description = _("Consulting Charges: {0}").format(appointment_doc.practitioner)
	item.income_account = get_income_account(appointment_doc.practitioner, appointment_doc.company)
	item.cost_center = healthconnect.get_cached_value("Company", appointment_doc.company, "cost_center")
	item.rate = charge
	item.amount = charge
	item.qty = 1
	item.reference_dt = "Patient Appointment"
	item.reference_dn = appointment_doc.name
	return item


def cancel_appointment(appointment_id):
	appointment = healthconnect.get_doc("Patient Appointment", appointment_id)
	if appointment.invoiced:
		sales_invoice = check_sales_invoice_exists(appointment)
		if sales_invoice and cancel_sales_invoice(sales_invoice):
			msg = _("Appointment {0} and Sales Invoice {1} cancelled").format(
				appointment.name, sales_invoice.name
			)
		else:
			msg = _("Appointment Cancelled. Please review and cancel the invoice {0}").format(
				sales_invoice.name
			)
		if healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups"):
			fee_validity = healthconnect.db.get_value("Fee Validity", {"patient_appointment": appointment.name})
			if fee_validity:
				healthconnect.db.set_value("Fee Validity", fee_validity, "status", "Cancelled")

	else:
		fee_validity = manage_fee_validity(appointment)
		msg = _("Appointment Cancelled.")
		if fee_validity:
			msg += _("Fee Validity {0} updated.").format(fee_validity.name)

	if appointment.event:
		event_doc = healthconnect.get_doc("Event", appointment.event)
		event_doc.status = "Cancelled"
		event_doc.save()

	healthconnect.msgprint(msg)


def cancel_sales_invoice(sales_invoice):
	if healthconnect.db.get_single_value("Healthcare Settings", "automate_appointment_invoicing"):
		if len(sales_invoice.items) == 1:
			if sales_invoice.docstatus.is_submitted():
				sales_invoice.cancel()
			return True
	return False


def check_sales_invoice_exists(appointment):
	sales_invoice = healthconnect.db.get_value(
		"Sales Invoice Item",
		{"reference_dt": "Patient Appointment", "reference_dn": appointment.name},
		"parent",
	)

	if sales_invoice:
		sales_invoice = healthconnect.get_doc("Sales Invoice", sales_invoice)
		return sales_invoice
	return False


@healthconnect.whitelist()
def get_availability_data(date, practitioner, appointment):
	"""
	Get availability data of 'practitioner' on 'date'
	:param date: Date to check in schedule
	:param practitioner: Name of the practitioner
	:return: dict containing a list of available slots, list of appointments and time of appointments
	"""

	date = getdate(date)
	weekday = date.strftime("%A")

	practitioner_doc = healthconnect.get_doc("Healthcare Practitioner", practitioner)

	check_employee_wise_availability(date, practitioner_doc)

	if practitioner_doc.practitioner_schedules:
		slot_details = get_available_slots(practitioner_doc, date)
	else:
		healthconnect.throw(
			_(
				"{0} does not have a Healthcare Practitioner Schedule. Add it in Healthcare Practitioner master"
			).format(practitioner),
			title=_("Practitioner Schedule Not Found"),
		)

	if not slot_details:
		# TODO: return available slots in nearby dates
		healthconnect.throw(
			_("Healthcare Practitioner not available on {0}").format(weekday), title=_("Not Available")
		)

	if isinstance(appointment, str):
		appointment = json.loads(appointment)
		appointment = healthconnect.get_doc(appointment)

	fee_validity = "Disabled"
	if healthconnect.db.get_single_value("Healthcare Settings", "enable_free_follow_ups"):
		fee_validity = check_fee_validity(appointment, date, practitioner)
		if not fee_validity and not appointment.get("__islocal"):
			fee_validity = get_fee_validity(appointment.get("name"), date) or None

	if appointment.invoiced:
		fee_validity = "Disabled"

	return {"slot_details": slot_details, "fee_validity": fee_validity}


def check_employee_wise_availability(date, practitioner_doc):
	employee = None
	if practitioner_doc.employee:
		employee = practitioner_doc.employee
	elif practitioner_doc.user_id:
		employee = healthconnect.db.get_value("Employee", {"user_id": practitioner_doc.user_id}, "name")

	if employee:
		# check holiday
		if is_holiday(employee, date):
			healthconnect.throw(_("{0} is a holiday".format(date)), title=_("Not Available"))

		# check leave status
		if "hrms" in healthconnect.get_installed_apps():
			leave_record = healthconnect.db.sql(
				"""select half_day from `tabLeave Application`
				where employee = %s and %s between from_date and to_date
				and docstatus = 1""",
				(employee, date),
				as_dict=True,
			)
			if leave_record:
				if leave_record[0].half_day:
					healthconnect.throw(
						_("{0} is on a Half day Leave on {1}").format(practitioner_doc.name, date),
						title=_("Not Available"),
					)
				else:
					healthconnect.throw(
						_("{0} is on Leave on {1}").format(practitioner_doc.name, date), title=_("Not Available")
					)


def get_available_slots(practitioner_doc, date):
	available_slots = slot_details = []
	weekday = date.strftime("%A")
	practitioner = practitioner_doc.name

	for schedule_entry in practitioner_doc.practitioner_schedules:
		validate_practitioner_schedules(schedule_entry, practitioner)
		practitioner_schedule = healthconnect.get_doc("Practitioner Schedule", schedule_entry.schedule)

		if practitioner_schedule and not practitioner_schedule.disabled:
			available_slots = []
			for time_slot in practitioner_schedule.time_slots:
				if weekday == time_slot.day:
					available_slots.append(time_slot)

			if available_slots:
				appointments = []
				allow_overlap = 0
				service_unit_capacity = 0
				# fetch all appointments to practitioner by service unit
				filters = {
					"practitioner": practitioner,
					"service_unit": schedule_entry.service_unit,
					"appointment_date": date,
					"status": ["not in", ["Cancelled"]],
				}

				if schedule_entry.service_unit:
					slot_name = f"{schedule_entry.schedule}"
					allow_overlap, service_unit_capacity = healthconnect.get_value(
						"Healthcare Service Unit",
						schedule_entry.service_unit,
						["overlap_appointments", "service_unit_capacity"],
					)
					if not allow_overlap:
						# fetch all appointments to service unit
						filters.pop("practitioner")
				else:
					slot_name = schedule_entry.schedule
					# fetch all appointments to practitioner without service unit
					filters["practitioner"] = practitioner
					filters.pop("service_unit")

				appointments = healthconnect.get_all(
					"Patient Appointment",
					filters=filters,
					fields=["name", "appointment_time", "duration", "status", "appointment_date"],
				)

				slot_details.append(
					{
						"slot_name": slot_name,
						"service_unit": schedule_entry.service_unit,
						"avail_slot": available_slots,
						"appointments": appointments,
						"allow_overlap": allow_overlap,
						"service_unit_capacity": service_unit_capacity,
						"tele_conf": practitioner_schedule.allow_video_conferencing,
					}
				)
	return slot_details


def validate_practitioner_schedules(schedule_entry, practitioner):
	if schedule_entry.schedule:
		if not schedule_entry.service_unit:
			healthconnect.throw(
				_(
					"Practitioner {0} does not have a Service Unit set against the Practitioner Schedule {1}."
				).format(
					get_link_to_form("Healthcare Practitioner", practitioner),
					healthconnect.bold(schedule_entry.schedule),
				),
				title=_("Service Unit Not Found"),
			)

	else:
		healthconnect.throw(
			_("Practitioner {0} does not have a Practitioner Schedule assigned.").format(
				get_link_to_form("Healthcare Practitioner", practitioner)
			),
			title=_("Practitioner Schedule Not Found"),
		)


@healthconnect.whitelist()
def update_status(appointment_id, status):
	healthconnect.db.set_value("Patient Appointment", appointment_id, "status", status)
	appointment_booked = True
	if status == "Cancelled":
		appointment_booked = False
		cancel_appointment(appointment_id)

	procedure_prescription = healthconnect.db.get_value(
		"Patient Appointment", appointment_id, "procedure_prescription"
	)
	if procedure_prescription:
		healthconnect.db.set_value(
			"Procedure Prescription", procedure_prescription, "appointment_booked", appointment_booked
		)


def send_confirmation_msg(doc):
	if healthconnect.db.get_single_value("Healthcare Settings", "send_appointment_confirmation"):
		message = healthconnect.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
		try:
			send_message(doc, message)
		except Exception:
			healthconnect.log_error(healthconnect.get_traceback(), _("Appointment Confirmation Message Not Sent"))
			healthconnect.msgprint(_("Appointment Confirmation Message Not Sent"), indicator="orange")


@healthconnect.whitelist()
def make_encounter(source_name, target_doc=None):
	doc = get_mapped_doc(
		"Patient Appointment",
		source_name,
		{
			"Patient Appointment": {
				"doctype": "Patient Encounter",
				"field_map": [
					["appointment", "name"],
					["patient", "patient"],
					["practitioner", "practitioner"],
					["medical_department", "department"],
					["patient_sex", "patient_sex"],
					["invoiced", "invoiced"],
					["company", "company"],
				],
			}
		},
		target_doc,
	)
	return doc


def send_appointment_reminder():
	if healthconnect.db.get_single_value("Healthcare Settings", "send_appointment_reminder"):
		remind_before = datetime.datetime.strptime(
			healthconnect.db.get_single_value("Healthcare Settings", "remind_before"), "%H:%M:%S"
		)
		reminder_dt = datetime.datetime.now() + datetime.timedelta(
			hours=remind_before.hour, minutes=remind_before.minute, seconds=remind_before.second
		)

		appointment_list = healthconnect.db.get_all(
			"Patient Appointment",
			{
				"appointment_datetime": ["between", (datetime.datetime.now(), reminder_dt)],
				"reminded": 0,
				"status": ["!=", "Cancelled"],
			},
		)

		for appointment in appointment_list:
			doc = healthconnect.get_doc("Patient Appointment", appointment.name)
			message = healthconnect.db.get_single_value("Healthcare Settings", "appointment_reminder_msg")
			send_message(doc, message)
			healthconnect.db.set_value("Patient Appointment", doc.name, "reminded", 1)


def send_message(doc, message):
	patient_mobile = healthconnect.db.get_value("Patient", doc.patient, "mobile")
	if patient_mobile:
		context = {"doc": doc, "alert": doc, "comments": None}
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		# jinja to string convertion happens here
		message = healthconnect.render_template(message, context)
		number = [patient_mobile]
		try:
			send_sms(number, message)
		except Exception as e:
			healthconnect.msgprint(_("SMS not sent, please check SMS Settings"), alert=True)


@healthconnect.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.

	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from healthconnect.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Patient Appointment", filters)

	data = healthconnect.db.sql(
		"""
		select
		`tabPatient Appointment`.name, `tabPatient Appointment`.patient,
		`tabPatient Appointment`.practitioner, `tabPatient Appointment`.status,
		`tabPatient Appointment`.duration,
		timestamp(`tabPatient Appointment`.appointment_date, `tabPatient Appointment`.appointment_time) as 'start',
		`tabAppointment Type`.color
		from
		`tabPatient Appointment`
		left join `tabAppointment Type` on `tabPatient Appointment`.appointment_type=`tabAppointment Type`.name
		where
		(`tabPatient Appointment`.appointment_date between %(start)s and %(end)s)
		and `tabPatient Appointment`.status != 'Cancelled' and `tabPatient Appointment`.docstatus < 2 {conditions}""".format(
			conditions=conditions
		),
		{"start": start, "end": end},
		as_dict=True,
		update={"allDay": 0},
	)

	for item in data:
		item.end = item.start + datetime.timedelta(minutes=item.duration)

	return data


@healthconnect.whitelist()
def get_procedure_prescribed(patient):
	return healthconnect.db.sql(
		"""
			SELECT
				pp.name, pp.procedure, pp.parent, ct.practitioner,
				ct.encounter_date, pp.practitioner, pp.date, pp.department
			FROM
				`tabPatient Encounter` ct, `tabProcedure Prescription` pp
			WHERE
				ct.patient=%(patient)s and pp.parent=ct.name and pp.appointment_booked=0
			ORDER BY
				ct.creation desc
		""",
		{"patient": patient},
	)


@healthconnect.whitelist()
def get_prescribed_therapies(patient):
	return healthconnect.db.sql(
		"""
			SELECT
				t.therapy_type, t.name, t.parent, e.practitioner,
				e.encounter_date, e.therapy_plan, e.medical_department
			FROM
				`tabPatient Encounter` e, `tabTherapy Plan Detail` t
			WHERE
				e.patient=%(patient)s and t.parent=e.name
			ORDER BY
				e.creation desc
		""",
		{"patient": patient},
	)


def update_appointment_status():
	# update the status of appointments daily
	appointments = healthconnect.get_all(
		"Patient Appointment", {"status": ("not in", ["Closed", "Cancelled"])}
	)

	for appointment in appointments:
		appointment_doc = healthconnect.get_doc("Patient Appointment", appointment.name)
		appointment_doc.set_status()
		appointment_doc.save()
