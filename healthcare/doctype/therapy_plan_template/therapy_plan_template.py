# -*- coding: utf-8 -*-
# Copyright (c) 2020, healthconnect Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import healthconnect
from healthconnect.model.document import Document
from healthconnect.utils import cint, flt

from healthcare.healthcare.doctype.therapy_type.therapy_type import make_item_price


class TherapyPlanTemplate(Document):
	def after_insert(self):
		if not self.link_existing_item:
			self.create_item_from_template()
		elif self.linked_item and self.total_amount:
			make_item_price(self.linked_item, self.total_amount)

	def validate(self):
		self.set_totals()

	def on_update(self):
		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return
		if (
			doc_before_save.item_name != self.item_name
			or doc_before_save.item_group != self.item_group
			or doc_before_save.description != self.description
		):
			self.update_item()

		if doc_before_save.therapy_types != self.therapy_types:
			self.update_item_price()

	def set_totals(self):
		total_sessions = 0
		total_amount = 0

		for entry in self.therapy_types:
			total_sessions += cint(entry.no_of_sessions)
			total_amount += flt(entry.amount)

		self.total_sessions = total_sessions
		self.total_amount = total_amount

	def create_item_from_template(self):
		uom = healthconnect.db.exists("UOM", "Nos") or healthconnect.db.get_single_value("Stock Settings", "stock_uom")

		item = healthconnect.get_doc(
			{
				"doctype": "Item",
				"item_code": self.item_code,
				"item_name": self.item_name,
				"item_group": self.item_group,
				"description": self.description,
				"is_sales_item": 1,
				"is_service_item": 1,
				"is_purchase_item": 0,
				"is_stock_item": 0,
				"show_in_website": 0,
				"is_pro_applicable": 0,
				"stock_uom": uom,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		make_item_price(item.name, self.total_amount)
		self.db_set("linked_item", item.name)

	def update_item(self):
		item_doc = healthconnect.get_doc("Item", {"item_code": self.linked_item})
		item_doc.item_name = self.item_name
		item_doc.item_group = self.item_group
		item_doc.description = self.description
		item_doc.ignore_mandatory = True
		item_doc.save(ignore_permissions=True)

	def update_item_price(self):
		item_price = healthconnect.get_doc("Item Price", {"item_code": self.linked_item})
		item_price.item_name = self.item_name
		item_price.price_list_rate = self.total_amount
		item_price.ignore_mandatory = True
		item_price.save(ignore_permissions=True)
