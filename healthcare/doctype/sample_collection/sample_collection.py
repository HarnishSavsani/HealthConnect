# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS and contributors
# For license information, please see license.txt


import healthconnect
from healthconnect import _
from healthconnect.model.document import Document
from healthconnect.utils import flt


class SampleCollection(Document):
	def validate(self):
		if flt(self.sample_qty) <= 0:
			healthconnect.throw(_("Sample Quantity cannot be negative or 0"), title=_("Invalid Quantity"))
