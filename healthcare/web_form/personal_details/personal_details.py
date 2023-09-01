import healthconnect
from healthconnect import _

no_cache = 1


def get_context(context):
	if healthconnect.session.user == "Guest":
		healthconnect.throw(_("You need to be logged in to access this page"), healthconnect.PermissionError)

	context.show_sidebar = True

	if healthconnect.db.exists("Patient", {"email": healthconnect.session.user}):
		patient = healthconnect.get_doc("Patient", {"email": healthconnect.session.user})
		context.doc = patient
		healthconnect.form_dict.new = 0
		healthconnect.form_dict.name = patient.name


def get_patient():
	return healthconnect.get_value("Patient", {"email": healthconnect.session.user}, "name")


def has_website_permission(doc, ptype, user, verbose=False):
	if doc.name == get_patient():
		return True
	else:
		return False
