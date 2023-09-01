import healthconnect


def execute():
	docs = healthconnect.db.get_all("Appointment Type Service Item")
	for doc in docs:
		healthconnect.get_doc("Appointment Type Service Item", doc.name)
		if doc.dn:
			doc.db_set("dt", "Medical Department")
