// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt

healthconnect.ui.form.on('Appointment Type', {
	refresh: function(frm) {
		frm.set_query('price_list', function() {
			return {
				filters: {'selling': 1}
			};
		});

		frm.set_query('dt', 'items', function() {
			if (['Department', 'Practitioner'].includes(frm.doc.allow_booking_for)) {
				return {
					filters: {'name': ['=', 'Medical Department']}
				};
			} else if (frm.doc.allow_booking_for === "Service Unit") {
				return {
					filters: {'name': ['=', 'Healthcare Service Unit']}
				};
			}
		});

		frm.set_query('dn', 'items', function(doc, cdt, cdn) {
			let child = locals[cdt][cdn];
			if (child.dt === 'Medical Department') {
				let item_list = doc.items
					.filter(item => item.dt === 'Medical Department')
					.map(({dn}) => dn);
				return {
					filters: [
						['Medical Department', 'name', 'not in', item_list]
					]
				};
			} else if (child.dt === 'Healthcare Service Unit') {
				let item_list = doc.items
					.filter(item => item.dt === 'Healthcare Service Unit')
					.map(({dn}) => dn);
				return {
					filters: [
						['Healthcare Service Unit', 'name', 'not in', item_list],
						['Healthcare Service Unit', 'allow_appointments', "=", 1],
					]
				};
			}
		});

		frm.set_query('op_consulting_charge_item', 'items', function() {
			return {
				filters: {
					is_stock_item: 0
				}
			};
		});

		frm.set_query('inpatient_visit_charge_item', 'items', function() {
			return {
				filters: {
					is_stock_item: 0
				}
			};
		});
	}
});

healthconnect.ui.form.on('Appointment Type Service Item', {
	op_consulting_charge_item: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (frm.doc.price_list && d.op_consulting_charge_item) {
			healthconnect.call({
				'method': 'healthconnect.client.get_value',
				args: {
					'doctype': 'Item Price',
					'filters': {
						'item_code': d.op_consulting_charge_item,
						'price_list': frm.doc.price_list
					},
					'fieldname': ['price_list_rate']
				},
				callback: function(data) {
					if (data.message.price_list_rate) {
						healthconnect.model.set_value(cdt, cdn, 'op_consulting_charge', data.message.price_list_rate);
					}
				}
			});
		}
	},

	inpatient_visit_charge_item: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (frm.doc.price_list && d.inpatient_visit_charge_item) {
			healthconnect.call({
				'method': 'healthconnect.client.get_value',
				args: {
					'doctype': 'Item Price',
					'filters': {
						'item_code': d.inpatient_visit_charge_item,
						'price_list': frm.doc.price_list
					},
					'fieldname': ['price_list_rate']
				},
				callback: function (data) {
					if (data.message.price_list_rate) {
						healthconnect.model.set_value(cdt, cdn, 'inpatient_visit_charge', data.message.price_list_rate);
					}
				}
			});
		}
	}
});
