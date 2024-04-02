
frappe.listview_settings['WhatsApp Message'] = {
	get_indicator: function(doc) {
        var status_color = {
			"sent" : "grey",
			"delivered" : "blue",
			"read" : "green",
			"failed" : "red",
			"" : "grey"
        };
		// Untuk filter
		var filter = filterString(doc.status)

		return [__(doc.status || ""), status_color[doc.status], filter];
	},
}

function filterString(status){
	return `status,=,${status}`
}
