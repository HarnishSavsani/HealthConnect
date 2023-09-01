# Copyright (c) 2021, healthconnect Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import healthconnect
from healthconnect import _
from healthconnect.model.document import Document


class TreatmentPlanTemplate(Document):
	def validate(self):
		self.validate_age()

	def validate_age(self):
		if self.patient_age_from and self.patient_age_from < 0:
			healthconnect.throw(_("Patient Age From cannot be less than 0"))
		if self.patient_age_to and self.patient_age_to < 0:
			healthconnect.throw(_("Patient Age To cannot be less than 0"))
		if self.patient_age_to and self.patient_age_from and self.patient_age_to < self.patient_age_from:
			healthconnect.throw(_("Patient Age To cannot be less than Patient Age From"))
