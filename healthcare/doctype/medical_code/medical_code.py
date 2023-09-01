# -*- coding: utf-8 -*-
# Copyright (c) 2017, healthconnect Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from healthconnect.model.document import Document


class MedicalCode(Document):
	def autoname(self):
		self.name = self.medical_code_standard + " " + self.code
