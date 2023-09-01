# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt


import healthconnect
from healthconnect import _
from healthconnect.model.document import Document


class VitalSigns(Document):
	def validate(self):
		self.set_title()

	def set_title(self):
		self.title = _("{0} on {1}").format(
			self.patient_name or self.patient, healthconnect.utils.format_date(self.signs_date)
		)[:100]
