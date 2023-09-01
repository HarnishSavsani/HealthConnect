import healthconnect
from healthconnect import DuplicateEntryError


def create_encounter(patient, practitioner, submit=False):
	encounter = healthconnect.new_doc("Patient Encounter")
	encounter.patient = patient
	encounter.practitioner = practitioner
	encounter.save()
	if submit:
		encounter.submit()
	return encounter
