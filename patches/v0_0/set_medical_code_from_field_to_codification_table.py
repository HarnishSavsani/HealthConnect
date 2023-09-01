import healthconnect


def execute():
	healthconnect.reload_doctype("Codification Table", force=True)
	healthconnect.reload_doctype("Medical Code Standard", force=True)

	doctypes = [
		"Lab Test",
		"Clinical Procedure",
		"Therapy Session",
		"Lab Test Template",
		"Clinical Procedure Template",
		"Therapy Type",
	]

	for doctype in doctypes:
		if healthconnect.db.has_column(doctype, "medical_code"):
			data = healthconnect.db.get_all(
				doctype,
				filters={"medical_code": ["!=", ""]},
				fields=["name", "medical_code"],
			)
			healthconnect.reload_doctype(doctype, force=True)
			for d in data:
				healthconnect.get_doc(
					{
						"doctype": "Codification Table",
						"parent": d["name"],
						"parentfield": "codification_table",
						"parenttype": doctype,
						"medical_code": d["medical_code"],
						"medical_code_standard": healthconnect.db.get_value(
							"Medical Code", d["medical_code"], "medical_code_standard"
						),
					}
				).insert()
