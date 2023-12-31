// Copyright (c) 2016, ESS
// License: See license.txt

healthconnect.query_reports["Lab Test Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": healthconnect.datetime.add_months(healthconnect.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": healthconnect.datetime.now_date(),
			"reqd": 1
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"default": healthconnect.defaults.get_default("Company"),
			"options": "Company"
		},
		{
			"fieldname": "template",
			"label": __("Lab Test Template"),
			"fieldtype": "Link",
			"options": "Lab Test Template"
		},
		{
			"fieldname": "patient",
			"label": __("Patient"),
			"fieldtype": "Link",
			"options": "Patient"
		},
		{
			"fieldname": "department",
			"label": __("Medical Department"),
			"fieldtype": "Link",
			"options": "Medical Department"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nCompleted\nApproved\nRejected"
		},
		{
			"fieldname": "invoiced",
			"label": __("Invoiced"),
			"fieldtype": "Check"
		}
	]
};
