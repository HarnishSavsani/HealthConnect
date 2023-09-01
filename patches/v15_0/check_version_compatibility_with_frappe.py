import click
import healthconnect


def execute():
	healthconnect_v = healthconnect.get_attr("healthconnect" + ".__version__")
	healthcare_v = healthconnect.get_attr("healthcare" + ".__version__")

	WIKI_URL = "https://github.com/healthconnect/health/wiki/changes-to-branching-and-versioning"

	if healthconnect_v.startswith("14") and healthcare_v.startswith("15"):
		message = f"""
			The `develop` branch of healthconnect Health is no longer compatible with healthconnect & ERPNext's `version-14`.
			Since you are using ERPNext/healthconnect `version-14` please switch healthconnect Health app's branch to `version-14` and then proceed with the update.\n\t
			You can switch the branch by following the steps mentioned here: {WIKI_URL}
		"""
		click.secho(message, fg="red")

		healthconnect.throw(message)  # nosemgrep
