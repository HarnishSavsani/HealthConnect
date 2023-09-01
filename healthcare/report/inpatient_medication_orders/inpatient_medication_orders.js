// Copyright (c) 2016, healthconnect Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

healthconnect.query_reports["Inpatient Medication Orders"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: healthconnect.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: healthconnect.datetime.add_months(healthconnect.datetime.get_today(), -1),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: healthconnect.datetime.now_date(),
			reqd: 1
		},
		{
			fieldname: "patient",
			label: __("Patient"),
			fieldtype: "Link",
			options: "Patient"
		},
		{
			fieldname: "service_unit",
			label: __("Healthcare Service Unit"),
			fieldtype: "Link",
			options: "Healthcare Service Unit",
			get_query: () => {
				var company = healthconnect.query_report.get_filter_value('company');
				return {
					filters: {
						'company': company,
						'is_group': 0
					}
				}
			}
		},
		{
			fieldname: "show_completed_orders",
			label: __("Show Completed Orders"),
			fieldtype: "Check",
			default: 1
		}
	]
};
