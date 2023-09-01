// Copyright (c) 2016, ESS and contributors
// For license information, please see license.txt

healthconnect.ui.form.on('Sample Collection', {
	refresh: function(frm) {
		if (healthconnect.defaults.get_default('create_sample_collection_for_lab_test')) {
			frm.add_custom_button(__('View Lab Tests'), function() {
				healthconnect.route_options = {'sample': frm.doc.name};
				healthconnect.set_route('List', 'Lab Test');
			});
		}
	}
});

healthconnect.ui.form.on('Sample Collection', 'patient', function(frm) {
	if(frm.doc.patient){
		healthconnect.call({
			'method': 'healthcare.healthcare.doctype.patient.patient.get_patient_detail',
			args: {
				patient: frm.doc.patient
			},
			callback: function (data) {
				var age = null;
				if (data.message.dob){
					age = calculate_age(data.message.dob);
				}
				healthconnect.model.set_value(frm.doctype,frm.docname, 'patient_age', age);
				healthconnect.model.set_value(frm.doctype,frm.docname, 'patient_sex', data.message.sex);
			}
		});
	}
});

var calculate_age = function(birth) {
	var	ageMS = Date.parse(Date()) - Date.parse(birth);
	var	age = new Date();
	age.setTime(ageMS);
	var	years =  age.getFullYear() - 1970;
	return `${years} ${__('Years(s)')} ${age.getMonth()} ${__('Month(s)')} ${age.getDate()} ${__('Day(s)')}`;
};
