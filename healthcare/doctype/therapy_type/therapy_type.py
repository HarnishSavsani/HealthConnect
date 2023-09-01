# -*- coding: utf-8 -*-
# Copyright (c) 2020, healthconnect Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json

import healthconnect
from healthconnect import _
from healthconnect.model.document import Document
from healthconnect.model.rename_doc import rename_doc
from healthconnect.utils import cint

from healthcare.healthcare.doctype.clinical_procedure_template.clinical_procedure_template import (
	make_item_price,
)


class TherapyType(Document):
	def validate(self):
		self.enable_disable_item()

	def after_insert(self):
		create_item_from_therapy(self)

	def on_update(self):
		if self.change_in_item:
			self.update_item_and_item_price()

	def enable_disable_item(self):
		if self.is_billable:
			if self.disabled:
				healthconnect.db.set_value("Item", self.item, "disabled", 1)
			else:
				healthconnect.db.set_value("Item", self.item, "disabled", 0)

	def update_item_and_item_price(self):
		if self.is_billable and self.item:
			item_doc = healthconnect.get_doc("Item", {"item_code": self.item})
			item_doc.item_name = self.item_name
			item_doc.item_group = self.item_group
			item_doc.description = self.description
			item_doc.disabled = 0
			item_doc.ignore_mandatory = True
			item_doc.save(ignore_permissions=True)

			if self.rate:
				if healthconnect.db.exists("Item Price", {"item_code": self.item}):
					item_price = healthconnect.get_doc("Item Price", {"item_code": self.item})
					item_price.item_name = self.item_name
					item_price.price_list_rate = self.rate
					item_price.ignore_mandatory = True
					item_price.save()
				else:
					make_item_price(self.item, self.rate)

		elif not self.is_billable and self.item:
			healthconnect.db.set_value("Item", self.item, "disabled", 1)

		self.db_set("change_in_item", 0)

	@healthconnect.whitelist()
	def add_exercises(self):
		exercises = self.get_exercises_for_body_parts()
		last_idx = max(
			[cint(d.idx) for d in self.get("exercises")]
			or [
				0,
			]
		)
		for i, d in enumerate(exercises):
			ch = self.append("exercises", {})
			ch.exercise_type = d.parent
			ch.idx = last_idx + i + 1

	def get_exercises_for_body_parts(self):
		body_parts = [entry.body_part for entry in self.therapy_for]

		exercises = healthconnect.db.sql(
			"""
				SELECT DISTINCT
					b.parent, e.name, e.difficulty_level
				FROM
				 	`tabExercise Type` e, `tabBody Part Link` b
				WHERE
					b.body_part IN %(body_parts)s AND b.parent=e.name
			""",
			{"body_parts": body_parts},
			as_dict=1,
		)

		return exercises


def create_item_from_therapy(doc):
	disabled = doc.disabled
	if doc.is_billable and not doc.disabled:
		disabled = 0

	uom = healthconnect.db.exists("UOM", "Unit") or healthconnect.db.get_single_value("Stock Settings", "stock_uom")

	item = healthconnect.get_doc(
		{
			"doctype": "Item",
			"item_code": doc.item_code,
			"item_name": doc.item_name,
			"item_group": doc.item_group,
			"description": doc.description,
			"is_sales_item": 1,
			"is_service_item": 1,
			"is_purchase_item": 0,
			"is_stock_item": 0,
			"show_in_website": 0,
			"is_pro_applicable": 0,
			"disabled": disabled,
			"stock_uom": uom,
		}
	).insert(ignore_permissions=True, ignore_mandatory=True)

	make_item_price(item.name, doc.rate)
	doc.db_set("item", item.name)


@healthconnect.whitelist()
def change_item_code_from_therapy(item_code, doc):
	doc = healthconnect._dict(json.loads(doc))

	if healthconnect.db.exists("Item", {"item_code": item_code}):
		healthconnect.throw(_("Item with Item Code {0} already exists").format(item_code))
	else:
		rename_doc("Item", doc.item, item_code, ignore_permissions=True)
		healthconnect.db.set_value("Therapy Type", doc.name, "item_code", item_code)
	return
