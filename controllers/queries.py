import healthconnect


@healthconnect.whitelist()
@healthconnect.validate_and_sanitize_search_inputs
def get_healthcare_service_units(doctype, txt, searchfield, start, page_len, filters):
	table = healthconnect.qb.DocType("Healthcare Service Unit")
	query = (
		healthconnect.qb.from_(table)
		.where(table.is_group == 0)
		.where(table.company == filters.get("company"))
		.where(table.name.like("%{0}%".format(txt)))
		.select("name")
		.get_sql()
	)

	if filters and filters.get("inpatient_record"):
		from healthcare.healthcare.doctype.inpatient_medication_entry.inpatient_medication_entry import (
			get_current_healthcare_service_unit,
		)

		service_unit = get_current_healthcare_service_unit(filters.get("inpatient_record"))

		# if the patient is admitted, then appointments should be allowed against the admission service unit,
		# inspite of it being an Inpatient Occupancy service unit
		if service_unit:
			query += " and (allow_appointments = 1 or name = {service_unit})".format(
				service_unit=healthconnect.db.escape(service_unit)
			)
		else:
			query += " and allow_appointments = 1"
	else:
		query += " and allow_appointments = 1"

	return healthconnect.db.sql(query, filters)
