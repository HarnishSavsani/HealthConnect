healthconnect.provide('healthconnect.dashboards.chart_sources');

healthconnect.dashboards.chart_sources["Department wise Patient Appointments"] = {
	method: "healthcare.healthcare.dashboard_chart_source.department_wise_patient_appointments.department_wise_patient_appointments.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: healthconnect.defaults.get_user_default("Company")
		}
	]
};
