// Copyright (c) 2021, healthconnect Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

healthconnect.ui.form.on('Treatment Plan Template', {
	refresh: function (frm) {
		frm.set_query('type', 'items', function () {
			return {
				filters: {
					'name': ['in', ['Lab Test Template', 'Clinical Procedure Template', 'Therapy Type']],
				}
			};
		});

		frm.set_query("practitioners", function () {
			if (frm.doc.medical_department) {
				return {
					filters: {
						"department": frm.doc.medical_department
					}
				};
			}
		});
	},
});
