"""
Quick demo of an imaginary Python software package
calling into the pySimPro framework.

TODO: Call for the generation of SimProObject classes.
"""
from requests.exceptions import HTTPError


# == Stub Classes ============================================================ #
# Unimportant. To be replaced by creating classes from ClassDescriptions.

class Company:
	"""Stub Class for Company"""
class CompanyCustomer:
	"""Stub Class for CompanyCustomer"""
class Job:
	"""Stub Class for Job"""
class JobCostCenter:
	"""Stub Class for JobCostCenter"""
class Site:
	"""Stub Class for Site"""
class Section:
	"""Stub Class for Section"""


# == Exceptions ============================================================== #

class JobRecordCreationError(Exception):
	"""Raised in the event of a failure to create a job record on SimPRO."""


# == Functions =============================================================== #

def create_site(customer: "CompanyCustomer", site_attributes: dict) -> "Site":
	""""""
	def set_name() -> str:
		"""Will attempt to form a valid name for a site if one is not passed."""
		name = ""
		if "Name" not in site_attributes:
			if (address := site_attributes.get("Address", None)) is not None:
				if (street_address := address.get("Address", None)) is not None:
					name = street_address.replace("\n", "")
					name = " ".join(name.split())
		else:
			# This path will get overridden in outer scope.
			name = site_attributes["Name"]
		return name

	record_attributes = {"Name": set_name()}
	record_attributes.update(site_attributes)  # "Name" override will occur here.

	# We need to create a job site, however SimPro sometimes has trouble with creating Sites.
	# This code will attempt 3 times to create a Site before failing.
	for _ in range(3):
		try:
			site = Site.create(customer, record_attributes)
		except HTTPError:
			continue
		else:
			break
	else:
		raise JobRecordCreationError

	return site


def create_job(
	company: "Company",
	customer: "CompanyCustomer",
	job_attributes: dict) -> "Job":
	"""Attempts to create a job record on SimPro.

	company: A valid Company object that exists on SimPRO.
	customer: A valid CompanyCustomer object that exists on SimPRO.
	job_attributes: A dict of attributes and values that SimPRO supports.
	"""
	record_attributes = {"Type": "Service", "Customer": customer.record_id}
	record_attributes.update(job_attributes)
	if "Site" not in record_attributes:
		# Create a site.
		site = create_site(customer, job_attributes)  # TODO: Need site specific attributes.
		job_attributes["Site"] = site.record_id
	try:
		job = Job.create(company, record_attributes)
	except Exception as err:
		raise err

	# Make sure the job has a section and create one if not.
	sections = Section.list_all(parent=job)
	if len(sections) < 1:
		section = Section.create(parent=job)
	else:
		section = sections[0]

	# Check if the Section has a JobCostCentre and create if not.
	job_cost_centers = JobCostCenter.list_all(parent=section)
	if len(job_cost_centers) < 1:
		job_cost_center_details = {"CostCenter": DEFAULT_COST_CENTER, "Name": "BOQ"}
		JobCostCenter.create(parent=section, attributes=job_cost_center_details)

	return job


# == Constants =============================================================== #

DEFAULT_COST_CENTER = 0
