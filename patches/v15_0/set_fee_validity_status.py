import healthconnect


def execute():
	validities = healthconnect.db.get_all("Fee Validity", {"status": "Pending"}, as_list=0)

	for fee_validity in validities:
		healthconnect.db.set_value("Fee Validity", fee_validity, "status", "Active")
