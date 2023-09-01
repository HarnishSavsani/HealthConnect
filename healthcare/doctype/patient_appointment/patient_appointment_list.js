/*
(c) ESS 2015-16
*/
healthconnect.listview_settings['Patient Appointment'] = {
	filters: [["status", "=", "Open"]],
	get_indicator: function(doc) {
		var colors = {
			"Open": "orange",
			"Scheduled": "yellow",
			"Closed": "green",
			"Cancelled": "red",
			"Expired": "grey",
			"Checked In": "blue",
			"Checked Out": "orange"
		};
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	}
};
