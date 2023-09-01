import healthconnect


def execute():
	company = healthconnect.get_all("Company", filters={"country": "India"})
	if not company:
		return

	from healthcare.regional.india.abdm.setup import setup

	setup()
