"""Webhook."""
import frappe
import json
import requests
import time
from werkzeug.wrappers import Response
import frappe.utils


# @frappe.whitelist(allow_guest=True)
# def webhook():
# 	"""Meta webhook."""
# 	if frappe.request.method == "GET":
# 		return get()
# 	return post()


# def get():
# 	"""Get."""
# 	hub_challenge = frappe.form_dict.get("hub.challenge")
# 	data = frappe.form_dict
# 	masukkan_ke_file("webhook_whatsapp", str(data))
	

# 	if frappe.form_dict.get("hub.verify_token") != "webhookmyjhltoken":
# 		frappe.throw("Verify token does not match")

# 	return Response(hub_challenge, status=200)

# def post():

# 	try:
# 		request = json.loads(frappe.request.data.decode('utf-8'))
# 		masukkan_ke_file("webhook_whatsapp_raw", str(request))
# 	except:
# 		# ambil request data dari parameter
# 		frappe.log_error(message = frappe.get_traceback(), title = ("TEST 1: {}".frappe.utils.now()))
	
# 	try:
# 		"""Post."""
# 		data = frappe.local.form_dict
# 		masukkan_ke_file("webhook_whatsapp", str(data))
# 	except:
# 		frappe.log_error(message = frappe.get_traceback(), title = ("TEST 2: {}".frappe.utils.now()))
		
# 	return Response("", status=200)

	


# """ ambil data nya pakai fungsi get_data"""
# def masukkan_ke_file(filename, data):
# 	f = open("{}.txt".format(filename), "a")
# 	f.write("{}\n".format(str(data)))
# 	f.close()
