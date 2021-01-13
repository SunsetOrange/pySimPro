"""
TODO: Investigate how to change all handling of URLs into a Path like objects.
"""
import os
from typing import List, Union, Any
from dataclasses import dataclass
import requests


# == Exceptions ============================================================== #

# == Functions =============================================================== #

def authenticate(base_url: str, credentials: dict) -> dict:
	"""Authenticates with SimPRO and creates auth headers for subsequent requests."""
	token_url = f"{base_url}/oauth2/token"
	response = requests.post(token_url, json=credentials)
	if not response.ok:
		response.raise_for_status()
	access_token = response.json()["access_token"]
	return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


# == Constants =============================================================== #

COMPANY_DOMAIN = os.environ["simpro_company_domain"]
BASE_URL = f"https://{COMPANY_DOMAIN}.simprosuite.com"
BASE_API_URL = f"{BASE_URL}/api/v1.0"

CLIENT_CREDENTIALS = {
	"grant_type": "client_credentials",
	"client_id": os.environ["simpro_client_id"],
	"client_secret": os.environ["simpro_client_secret"]}
AUTH_HEADERS = authenticate(BASE_URL, CLIENT_CREDENTIALS)


# == Classes ================================================================= #

class Parentless:
	"""A special class for assigning to a SimProObject's parent parameter,
	if that class normally has no parent, such as the the Company class.
	"""
	obj_url = BASE_API_URL


# == Abstract Base Classes =================================================== #

class SimProObject:
	"""Abstract Base Class for all SimPRO objects."""
	@staticmethod
	def _columns_to_params(columns: Union[List[str], None]) -> str:
		"""A function for converting a list of desired columns to a request's params value.

		columns -- a list of strings of the attributes we want SimPRO to respond with.
		return -- a string representing the required params value for the request.
		"""
		columns = [] if columns is None else columns
		columns.append("ID")  # Requested attributes must always include the object's IDs.
		columns = set(columns)  # Cast attributes to a Set to clear duplicates.
		# Is the order important? Remember that Sets don't maintain order!
		params = ",".join(columns)
		return params

	@property
	def type_url_suffix(self):
		"""This dummy property forces all derived classes to implement a class variable.

		eg.
		class XXXX(SimProObject):
			type_url_suffix = "/xxxx/"

			def ...
		"""
		raise NotImplementedError("A type_url_suffix has not been implemented for this SimProObject subclass.")

	@property
	def obj_url(self) -> str:
		"""Returns a request URL for this object specifically.

		Calling this function will append self's type_url_suffix and record_id
		to the returned value of the parent's own obj_url method. Depending on
		how deeply nested this object's parentage is, this function may be
		recursively called several layers deep. Eventually, a class without a
		parent will be reached (like Company). The Parentless class	should be
		assigned to that last object's parent parameter. Parentless will then
		return the base BASE_API_URL as its obj_url, completing the request URL.
		"""
		request_url = self.parent.obj_url + type(self).type_url_suffix + str(self.record_id)
		return request_url

	# def _type_url(cls, parent) -> str:
	# 	"""Assembles and returns the URL required to perform a 'list all __' GET request.
	#
	# 	cls -- The class of the child objects we will be requesting.
	# 	parent -- the parent object of the child objects we will be requesting.
	# 	return -- a request URL required to perform a 'list all __' GET request.
	#
	# 	Primarily used by the _list_all method to request a complete list of all
	# 	objects of this type from SimPRO, under the parent object. Generally,
	# 	SimProObjects have parents, and this function will call the parent's
	# 	obj_url method and append the type_url_suffix to the returned value.
	# 	However, in the case of parentless classes like the Company class, the
	# 	Parentless class should be assigned to the object's parent parameter.
	# 	This will pass in the base API_URL as the url prefix.
	# 	"""
	# 	return parent.obj_url + cls.type_url_suffix

	@classmethod
	def _list_all(cls, parent, columns: List[str]) -> list:
		"""Returns a list of all child objects of this type from a parent object from SimPRO.

		cls -- the object type of the children to list.
		parent -- a required object that is the parent of the child objects to list.
			(must have a real and valid id)
		columns -- a list of strings of attributes to retrieve from SimPRO for each object.

		return -- a list of child objects of type cls.
		"""
		columns_param = cls._columns_to_params(columns)
		params = {"columns": columns_param, "pageSize": 250, "page": 1, "orderby": "ID"}
		request_url = parent.obj_url + cls.type_url_suffix
		child_objects = []
		while params["page"] is not None:
			# TODO: Change this to a log, not a print statement.
			print(f"Requesting {parent.__class__.__name__}'s {cls.__name__} page {params['page']}")
			response = requests.get(request_url, params=params, headers=AUTH_HEADERS)
			if not response.ok:
				response.raise_for_status()
			for obj_attributes in response.json():
				record_id = obj_attributes.pop("ID")
				simpro_object = cls(record_id, parent, obj_attributes)
				child_objects.append(simpro_object)

			if "next" in response.links:
				# This will increment the page number for subsequent requests.
				# If the page key was not set for the initial request, then it is assumed it was 1.
				params["page"] = params.get("page", 1) + 1
			else:
				params["page"] = None

		# TODO: Change this to a log, not a print statement.
		print(f"Completed retrieving {cls.__name__}(s)\n")
		return child_objects

	@classmethod
	def list_all(cls, parent, columns: List[str] = None) -> list:
		"""Encapsulates _list_all. Allows for subclasses to adjust specific attribute retrieval."""
		columns = [] if columns is None else columns
		children = cls._list_all(parent, columns)
		return children

	@classmethod
	def _create(cls, parent, attributes: dict):
		"""Creates a new record on the SimPRO server from this object."""
		request_url = parent.obj_url + cls.type_url_suffix
		response = requests.post(request_url, json=attributes, headers=AUTH_HEADERS)
		if not response.ok:
			response.raise_for_status()
		obj_attributes = response.json()
		record_id = obj_attributes.pop("ID")
		simpro_obj = cls(record_id, parent, obj_attributes)
		return simpro_obj

	@classmethod
	def create(cls, parent, attributes: dict = None):
		"""Encapsulates _create. Allows for subclasses to adjust specific attribute writes."""
		attributes = dict() if attributes is None else attributes
		simpro_obj = cls._create(parent, attributes)
		return simpro_obj

	@classmethod
	def _retrieve(cls, record_id: int, parent, columns: List[str] = None):
		"""Retrieves an object from SimPRO and its desired attributes.

		Requires an existing valid record id.
		"""
		columns_param = cls._columns_to_params(columns)
		params = {"columns": columns_param}
		request_url = parent.obj_url + cls.type_url_suffix + str(record_id)
		response = requests.get(request_url, params=params, headers=AUTH_HEADERS)
		if not response.ok:
			response.raise_for_status()
		obj_attributes = response.json()
		record_id = obj_attributes.pop("ID")
		simpro_obj = cls(record_id, parent, obj_attributes)
		return simpro_obj

	@classmethod
	def retrieve(cls, record_id: int, parent, columns: List[str] = None):
		"""Encapsulates _retrieve. Allows for subclasses to overwrite normal behaviour."""
		columns = [] if columns is None else columns
		simpro_obj = cls._retrieve(record_id, parent, columns)
		return simpro_obj

	def __init__(self, record_id: int, parent, attributes: dict = None):
		"""Creates a new SimProObject locally.

		DOES NOT confirm existence, upload to,
		or download information from the server.
		"""
		self.parent = parent
		self.record_id = record_id
		self.attributes = dict() if attributes is None else attributes

	# def _update(self):
	# 	"""Upload attribute changes to the SimPRO server."""
	# 	raise NotImplementedError

	# def _delete(self):
	# 	"""Delete an object on the SimPRO server."""
	# 	raise NotImplementedError


# == Sub Classes ============================================================= #

class Company(SimProObject):
	"""Top level SimPRO container object."""
	type_url_suffix = "/companies/"
	columns = {
		"ID": int,
		"Name": str,
		"Phone": str,
		"Fax": str,
		"Email": str,
		"Address": {
			"Line1": str,
			"Line2": str
			},
		"BillingAddress": {
			"Line1": str,
			"Line2": str
			},
		"EIN": str,
		"CompanyNo": str,
		"Licence": str,
		"Website": str,
		"Banking": {
			"Bank": str,
			"BranchCode": str,
			"AccountName": str,
			"RoutingNo": str,
			"AccountNo": str,
			"IBAN": str,
			"SwiftCode": str
			},
		"CISCertNo": str,
		"EmployerTaxRefNo": str,
		"Timezone": str,
		"TimezoneOffset": str,
		"DefaultLanguage": str,
		"Template": bool,
		"MultiCompanyLabel": str,
		"MultiCompanyColor": str,
		"Currency": str,
		"Country": str,
		"TaxName": str,
		"UIDateFormat": str,
		"UITimeFormat": str,
		"ScheduleFormat": int,
		"SingleCostCenterMode": bool,
		"DateModified": str,
		"DefaultCostCenter": {
			"ID": int,
			"Name": str
			}
		}

	@classmethod
	def list_all(cls, parent, columns: List[str] = None):
		"""Overwrites list_all to force Name as an attribute."""
		columns = [] if columns is None else columns
		columns.insert(0, "Name")
		return cls._list_all(parent, columns)

	def __init__(self, record_id: int, parent: Parentless = None, attributes: dict = None):
		"""Creates a new Company object locally

		DOES NOT confirm existence, upload to,
		or download information from the server.
		"""
		record_id = 0 if not record_id else record_id
		# Defaults to first company if None or False.
		parent = Parentless() if parent is None else parent
		# Should also work if the class is not instantiated.
		attributes = dict() if attributes is None else attributes
		super().__init__(record_id, parent=parent, attributes=attributes)


# == Class Factory =========================================================== #

@dataclass
class ClassDescription:
	"""A meta class for a description of a class derived from SimProObject.

	name -- the name of the new class
	bases -- any base classes to derive from other than SimProObject
	type_url_suffix -- a compulsory URL component for generating a request URL
	docstring -- optional str for the new class
	attributes -- an optional list of valid attributes SimPRO supports for this
		database record
		Note: This isn't the python class's attrs, but rather the SimPRO record
		attributes which are accessed via a request's params value.
	attrs -- a dict of attributes and values to the assign to the new class
	"""
	name: str
	bases: Union[tuple, None]
	type_url_suffix: str
	docstring: str = None
	attributes: List[str] = None  # See this classes docstring!
	definitions: dict[str, Any] = None

	@staticmethod
	def build_classes(class_descriptions) -> List[type]:
		"""Class factory function for building all the SimPRO object classes.

		A static method that will convert class descriptions into actual Types.
		class_descriptions -- a list of ClassDescription to be converted to Types

		return -- a list of Types
		"""
		classes = []
		for cls in class_descriptions:
			bases = [SimProObject]  # All classes are derived from SimProObject.
			if cls.bases:
				bases.extend(cls.bases)
			definitions = {"type_url_suffix": cls.type_url_suffix}
			if cls.docstring:
				definitions["__doc__"] = cls.docstring
			if cls.attributes:
				definitions["attributes"] = cls.attributes
			if isinstance(cls.definitions, dict):
				definitions.update(cls.definitions)

			# New classes are created by providing a class name, a list of
			# derived classes and a dict of definitions, which is copied to the
			# new class's __dict__ attribute.
			new_class = type(cls.name, tuple(bases), definitions)
			classes.append(new_class)
		return classes


CLASS_DESCRIPTIONS = [
	ClassDescription("Company", None, "/companies/", "A Parentless SimPRO Type representing a company."),
	ClassDescription("Contact", None, "/contacts/", "Child of Company."),
	ClassDescription("Contractor", None, "/contractors/", "Child of Company."),
	# ClassDescription("ContractorAttachment", None, "", ""),
	# ClassDescription("ContractorAttachmentFolder", None, "", ""),
	# ClassDescription("ContractorLicence", None, "", ""),
	# ClassDescription("ContractorTimesheet", None, "", ""),
	# ClassDescription("Customer", None, "", ""),
	ClassDescription("CompanyCustomer", None, "/customers/companies/", "Child of Company."),
	# ClassDescription("CustomerAttachment", None, "", ""),
	# ClassDescription("CustomerAttachmentFolder", None, "", ""),
	# ClassDescription("CustomerContact", None, "", ""),
	# ClassDescription("CustomerNote", None, "", ""),
	# ClassDescription("CustomerNoteAttachment", None, "", ""),
	# ClassDescription("CustomerResponseTime", None, "", ""),
	ClassDescription("Employee", None, "/employees/", "Child of Company."),
	# ClassDescription("EmployeeAttachment", None, "", ""),
	# ClassDescription("EmployeeAttachmentFolder", None, "", ""),
	# ClassDescription("EmployeeLicence", None, "", ""),
	# ClassDescription("EmployeeTimesheet", None, "", ""),
	ClassDescription("Site", None, "/sites/", "Child of Company.", [
		"Address",  # Street address
		"City",  # Locality
		"State",  # QLD
		"PostalCode",
		"Country"  # Australia
		]),
	# ClassDescription("SiteAttachment", None, "", ""),
	# ClassDescription("SiteAttachmentFolder", None, "", ""),
	# ClassDescription("SiteContact", None, "", ""),
	# ClassDescription("SitePreferredTechnician", None, "", ""),
	ClassDescription("Staff", None, "/staff/", "Child of Company."),
	ClassDescription("Vendor", None, "/vendors/", "Child of Company."),
	# ClassDescription("VendorAttachment", None, "", ""),
	# ClassDescription("VendorAttachmentFolder", None, "", ""),
	# ClassDescription("VendorBranch", None, "", ""),
	# ClassDescription("VendorContact", None, "", ""),
	# ClassDescription("ContractorJob", None, "", ""),
	# ClassDescription("ContractorJobAttachment", None, "", ""),
	# ClassDescription("ContractorJobAttachmentFolder", None, "", ""),
	# ClassDescription("ContractorQuote", None, "", ""),
	# ClassDescription("ContractorQuoteAttachment", None, "", ""),
	# ClassDescription("ContractorQuoteAttachmentFolder", None, "", ""),
	ClassDescription("Job", None, "/jobs/", "Child of Company.", [
		"Type",
		"Customer",
		"CustomerContact",
		"AdditionalContacts"
		"Site",
		"SiteContact",
		"OrderNo",
		"RequestNo",
		"Name",
		"Description",
		"Notes",
		"DateIssued",
		"DueDate",
		"DueTime",
		"Tags",
		"Salesperson",
		"ProjectManager",
		"Technician",
		"Stage",
		"Status",
		"ResponseTime",
		"IsVariation",
		"LinkedVariations",
		"ConvertedFromQuote",
		"DateModified",
		"Total",
		"Totals",
		]),
	# ClassDescription("JobAttachment", None, "", ""),
	# ClassDescription("JobAttachmentFolder", None, "", ""),
	# ClassDescription("JobNote", None, "", ""),
	# ClassDescription("JobNoteAttachment", None, "", ""),
	ClassDescription("JobSection", None, "/sections/", "Child of Job."),
	# ClassDescription("CustomerInvoice", None, "", ""),
	# ClassDescription("JobTimeline", None, "", ""),
	ClassDescription("JobCostCenter", None, "/costCenters/", "Child of Section."),
	# ClassDescription("JobCostCenterAsset", None, "", ""),
	# ClassDescription("JobCostCenterCatalogItem", None, "", ""),
	# ClassDescription("JobCostCenterLaborItem", None, "", ""),
	# ClassDescription("JobCostCenterOne-OffItem", None, "", ""),
	# ClassDescription("JobCostCenterPrebuildItem", None, "", ""),
	# ClassDescription("JobCostCenterServiceFee", None, "", ""),
	# ClassDescription("JobCostCenterStockItem", None, "", ""),
	# ClassDescription("Lead", None, "", ""),
	# ClassDescription("LeadAttachment", None, "", ""),
	# ClassDescription("LeadAttachmentFolder", None, "", ""),
	ClassDescription("Quote", None, "/quotes/", "Child of Company."),
	# ClassDescription("QuoteAttachment", None, "", ""),
	# ClassDescription("QuoteAttachmentFolder", None, "", ""),
	# ClassDescription("QuoteNote", None, "", ""),
	# ClassDescription("QuoteNoteAttachment", None, "", ""),
	ClassDescription("QuoteSection", None, "/sections/", "Child of Quote."),
	ClassDescription("JobTimeline", None, "/timelines/", "Child of Job."),
	# ClassDescription("QuoteCostCenter", None, "", ""),
	# ClassDescription("QuoteCostCenterAsset", None, "", ""),
	# ClassDescription("QuoteCostCenterCatalogItem", None, "", ""),
	# ClassDescription("QuoteCostCenterLaborItem", None, "", ""),
	# ClassDescription("QuoteCostCenterOne-OffItem", None, "", ""),
	# ClassDescription("QuoteCostCenterPrebuildItem", None, "", ""),
	# ClassDescription("QuoteCostCenterServiceFee", None, "", ""),
	ClassDescription("Catalog", None, "/catalogs/", "Child of Company."),
	# ClassDescription("CatalogAttachment", None, "", ""),
	# ClassDescription("CatalogAttachmentFolder", None, "", ""),
	# ClassDescription("CatalogGroup", None, "", ""),
	# ClassDescription("CatalogItemVendor", None, "", ""),
	# ClassDescription("CatalogInventory", None, "", ""),
	# ClassDescription("InventoryJournal", None, "", ""),
	# ClassDescription("StorageDevice", None, "", ""),
	# ClassDescription("StockItem", None, "", ""),
	# ClassDescription("StockTransfer", None, "", ""),
	ClassDescription("Prebuild", None, "/prebuilds/", "Child of CostCenter."),
	ClassDescription("SetPricePrebuild", None, "/prebuilds/setPrice/", "Child of Company."),
	# ClassDescription("PrebuildGroup", None, "", ""),
	# ClassDescription("PrebuildCatalog", None, "", ""),
	# ClassDescription("PrebuildAttachment", None, "", ""),
	# ClassDescription("PrebuildAttachmentFolder", None, "", ""),
	# ClassDescription("VendorOrder", None, "", ""),
	# ClassDescription("VendorOrderAttachment", None, "", ""),
	# ClassDescription("VendorOrderAttachmentFolder", None, "", ""),
	# ClassDescription("VendorOrderOrderItem", None, "", ""),
	# ClassDescription("VendorOrderItemAllocation", None, "", ""),
	# ClassDescription("ContractorInvoice", None, "", ""),
	ClassDescription("CustomerInvoice", None, "/customerInvoices/", "Child of Company."),
	# ClassDescription("CustomerPayment", None, "", ""),
	# ClassDescription("VendorReceipt", None, "", ""),
	# ClassDescription("VendorReceiptItemAllocation", None, "", ""),
	# ClassDescription("VendorCredit", None, "", ""),
	# ClassDescription("VendorCreditItem", None, "", ""),
	# ClassDescription("RecurringInvoice", None, "", ""),
	# ClassDescription("RecurringInvoiceSection", None, "", ""),
	# ClassDescription("RecurringInvoiceTimeline", None, "", ""),
	# ClassDescription("RecurringInvoiceAttachment", None, "", ""),
	# ClassDescription("RecurringInvoiceAttachmentFolder", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCenters", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCentersCatalogItem", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCentersLaborItem", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCentersOne-OffItem", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCentersPrebuildItem", None, "", ""),
	# ClassDescription("RecurringInvoiceCostCentersServiceFee", None, "", ""),
	ClassDescription("CostCenter", None, "/setup/accounts/costCenters/", "Child of Company."),
	# ClassDescription("BusinessGroup", None, "", ""),
	# ClassDescription("PaymentMethod", None, "", ""),
	# ClassDescription("AccountingCategory", None, "", ""),
	# ClassDescription("Activity", None, "", ""),
	# ClassDescription("AssetType", None, "", ""),
	# ClassDescription("AssetTypeServiceLevel", None, "", ""),
	# ClassDescription("AssetTypeAttachment", None, "", ""),
	# ClassDescription("AssetTypeAttachmentFolder", None, "", ""),
	# ClassDescription("FailurePoint", None, "", ""),
	# ClassDescription("Recommendation", None, "", ""),
	# ClassDescription("TestReading", None, "", ""),
	# ClassDescription("ServiceLevel", None, "", ""),
	# ClassDescription("QuoteArchiveReason", None, "", ""),
	# ClassDescription("Commission", None, "", ""),
	# ClassDescription("Currency", None, "", ""),
	# ClassDescription("__CustomField__", None, "", ""),
	# ClassDescription("CustomerGroup", None, "", ""),
	# ClassDescription("CustomerProfile", None, "", ""),
	# ClassDescription("FitTime", None, "", ""),
	# ClassDescription("LaborRate", None, "", ""),
	# ClassDescription("ScheduleRate", None, "", ""),
	# ClassDescription("ServiceFee", None, "", ""),
	# ClassDescription("PricingTier", None, "", ""),
	ClassDescription("UnitsOfMeasurement", None, "/setup/materials/uoms/", "Child of Company."),
	# ClassDescription("ResponseTime", None, "", ""),
	# ClassDescription("SecurityGroup", None, "", ""),
	# ClassDescription("CustomerInvoiceStatusCodes", None, "", ""),
	# ClassDescription("ProjectStatusCode", None, "", ""),
	# ClassDescription("VendorOrderStatusCode", None, "", ""),
	# ClassDescription("CustomerTag", None, "", ""),
	ClassDescription("ProjectTag", None, "/setup/tags/projects/", "Child of Company."),
	# ClassDescription("TaskCategory", None, "", ""),
	# ClassDescription("TaxCode", None, "", ""),
	# ClassDescription("CombineTaxCode", None, "", ""),
	# ClassDescription("ComponentTaxCode", None, "", ""),
	# ClassDescription("SingleTaxCode", None, "", ""),
	# ClassDescription("Team", None, "", ""),
	# ClassDescription("WebhookSubscription", None, "", ""),
	# ClassDescription("Zone", None, "", ""),
	# ClassDescription("CostToCompleteOperationView", None, "", ""),
	# ClassDescription("CostToCompleteFinancialView", None, "", ""),
	ClassDescription("Company", None, "/companies/", "Child of Parentless."),
	# ClassDescription("CustomerAsset", None, "", ""),
	# ClassDescription("AssetServiceLevel", None, "", ""),
	# ClassDescription("AssetTestHistory", None, "", ""),
	# ClassDescription("AssetAttachment", None, "", ""),
	# ClassDescription("AssetAttachmentFolder", None, "", ""),
	# ClassDescription("Info", None, "", ""),
	# ClassDescription("CustomerInvoiceLog", None, "", ""),
	# ClassDescription("JobLog", None, "", ""),
	# ClassDescription("QuoteLog", None, "", ""),
	# ClassDescription("VendorOrderLog", None, "", ""),
	# ClassDescription("PlantAndEquipment", None, "", ""),
	# ClassDescription("PlantType", None, "", ""),
	# ClassDescription("Schedule", None, "", ""),
	# ClassDescription("ActivitySchedule", None, "", ""),
	# ClassDescription("LeadSchedule", None, "", ""),
	# ClassDescription("QuoteCostCenterSchedule", None, "", ""),
	# ClassDescription("JobCostCenterSchedule", None, "", ""),
	# ClassDescription("Task", None, "", ""),
	# ClassDescription("TaskAttachment", None, "", ""),
	# ClassDescription("TaskAttachmentFolder", None, "", ""),
	# ClassDescription("CustomerTask", None, "", ""),
	# ClassDescription("JobTask", None, "", ""),
	# ClassDescription("JobCostCenterTask", None, "", ""),
	# ClassDescription("QuoteTask", None, "", ""),
	# ClassDescription("QuoteCostCenterTask", None, "", ""),
	# ClassDescription("JobWorkOrder", None, "", ""),
	# ClassDescription("JobWorkOrderAsset", None, "", ""),
	# ClassDescription("WorkOrderAttachment", None, "", ""),
	# ClassDescription("QuoteWorkOrder", None, "", ""),
	# ClassDescription("QuoteWorkOrderAsset", None, "", ""),
	]
