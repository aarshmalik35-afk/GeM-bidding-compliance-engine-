"""
MOCK GOVERNMENT REGISTRY
------------------------
For the hackathon prototype we simulate the databases a procurement officer
would otherwise check manually (GSTN portal, NSDL PAN, Udyam portal, EPFO/ESIC,
NSIC, debarment list). Each is a simple in-memory dict.

WHY MOCKED: Real integrations (GSTN search API, PAN verification via
Protean/NSDL, Udyam Assist API, EPFO employer API) need paid subscriptions or
MeitY/NIC sanctioned access that you won't get approved before a hackathon
deadline. Keep the function signatures below stable — swap the body of each
`check_*` function for a real HTTP call later and nothing else in the app
needs to change.
"""

from typing import Optional
from app.models import CheckResult, DocType

# ---- Sample "registered" records for demo purposes ----
GST_DB = {
    "27AAAPL1234C1ZV": {"legal_name": "ACME TECH SOLUTIONS PVT LTD", "status": "Active", "return_filing": "Regular"},
    "07BBBPL5678D1Z2": {"legal_name": "SAMPLE ENGINEERING WORKS", "status": "Active", "return_filing": "Regular"},
}

PAN_DB = {
    "AAAPL1234C": {"name": "ACME TECH SOLUTIONS PVT LTD", "category": "Company", "itr_filed": True},
    "BBBPL5678D": {"name": "SAMPLE ENGINEERING WORKS", "category": "Partnership", "itr_filed": True},
}

UDYAM_DB = {
    "UDYAM-DL-01-0012345": {"enterprise_name": "ACME TECH SOLUTIONS PVT LTD", "category": "Small", "valid": True},
}

EPFO_DB = {
    "DLCPM1234567000": {"establishment_name": "ACME TECH SOLUTIONS PVT LTD", "status": "Active"},
}

NSIC_DB = {
    "NSIC-REG-998877": {"enterprise_name": "SAMPLE ENGINEERING WORKS", "valid": True},
}

DEBARRED_ENTITIES = {
    "BLACKLISTED TRADERS PVT LTD",
    "SAMPLE ENGINEERING WORKS",  # deliberately included so the demo can show a FAIL case
}


def check_gst(gstin: Optional[str]) -> CheckResult:
    if not gstin:
        return CheckResult(check_name="GST Registration", doc_type=DocType.GST,
                            status="NOT_PROVIDED", detail="No GSTIN submitted.", source="mock_registry")
    record = GST_DB.get(gstin.strip().upper())
    if not record:
        return CheckResult(check_name="GST Registration", doc_type=DocType.GST,
                            status="FAIL", detail=f"GSTIN {gstin} not found in registry.", source="mock_registry")
    if record["status"] != "Active" or record["return_filing"] != "Regular":
        return CheckResult(check_name="GST Registration", doc_type=DocType.GST,
                            status="WARNING",
                            detail=f"GSTIN active but return filing status is '{record['return_filing']}'.",
                            source="mock_registry")
    return CheckResult(check_name="GST Registration", doc_type=DocType.GST,
                        status="PASS", detail=f"GSTIN active for {record['legal_name']}, returns regular.",
                        source="mock_registry")


def check_pan(pan: Optional[str]) -> CheckResult:
    if not pan:
        return CheckResult(check_name="PAN / Income Tax", doc_type=DocType.PAN,
                            status="NOT_PROVIDED", detail="No PAN submitted.", source="mock_registry")
    record = PAN_DB.get(pan.strip().upper())
    if not record:
        return CheckResult(check_name="PAN / Income Tax", doc_type=DocType.PAN,
                            status="FAIL", detail=f"PAN {pan} not found / could not be verified.", source="mock_registry")
    if not record["itr_filed"]:
        return CheckResult(check_name="PAN / Income Tax", doc_type=DocType.PAN,
                            status="WARNING", detail="PAN valid but ITR filing not confirmed.", source="mock_registry")
    return CheckResult(check_name="PAN / Income Tax", doc_type=DocType.PAN,
                        status="PASS", detail=f"PAN verified for {record['name']}, ITR filing confirmed.",
                        source="mock_registry")


def check_udyam(udyam_number: Optional[str]) -> CheckResult:
    if not udyam_number:
        return CheckResult(check_name="Udyam / MSME Registration", doc_type=DocType.UDYAM,
                            status="NOT_PROVIDED", detail="No Udyam number submitted (optional unless claiming MSME benefits).",
                            source="mock_registry")
    record = UDYAM_DB.get(udyam_number.strip().upper())
    if not record or not record["valid"]:
        return CheckResult(check_name="Udyam / MSME Registration", doc_type=DocType.UDYAM,
                            status="FAIL", detail=f"Udyam number {udyam_number} not found or invalid.",
                            source="mock_registry")
    return CheckResult(check_name="Udyam / MSME Registration", doc_type=DocType.UDYAM,
                        status="PASS",
                        detail=f"Valid {record['category']} enterprise registration for {record['enterprise_name']}.",
                        source="mock_registry")


def check_epfo(epfo_code: Optional[str]) -> CheckResult:
    if not epfo_code:
        return CheckResult(check_name="EPFO Compliance", doc_type=DocType.EPFO,
                            status="NOT_PROVIDED", detail="No EPFO establishment code submitted.", source="mock_registry")
    record = EPFO_DB.get(epfo_code.strip().upper())
    if not record or record["status"] != "Active":
        return CheckResult(check_name="EPFO Compliance", doc_type=DocType.EPFO,
                            status="FAIL", detail=f"EPFO code {epfo_code} not active/found.", source="mock_registry")
    return CheckResult(check_name="EPFO Compliance", doc_type=DocType.EPFO,
                        status="PASS", detail=f"EPFO registration active for {record['establishment_name']}.",
                        source="mock_registry")


def check_nsic(nsic_number: Optional[str]) -> CheckResult:
    if not nsic_number:
        return CheckResult(check_name="NSIC Registration", doc_type=DocType.NSIC,
                            status="NOT_PROVIDED", detail="No NSIC registration submitted (optional).", source="mock_registry")
    record = NSIC_DB.get(nsic_number.strip().upper())
    if not record or not record["valid"]:
        return CheckResult(check_name="NSIC Registration", doc_type=DocType.NSIC,
                            status="FAIL", detail=f"NSIC number {nsic_number} not found/invalid.", source="mock_registry")
    return CheckResult(check_name="NSIC Registration", doc_type=DocType.NSIC,
                        status="PASS", detail=f"NSIC registration valid for {record['enterprise_name']}.",
                        source="mock_registry")


def check_debarment(bidder_name: str) -> CheckResult:
    if bidder_name.strip().upper() in DEBARRED_ENTITIES:
        return CheckResult(check_name="Blacklisting / Debarment", doc_type=DocType.OTHER,
                            status="FAIL", detail=f"{bidder_name} appears on the debarment list.",
                            source="mock_registry")
    return CheckResult(check_name="Blacklisting / Debarment", doc_type=DocType.OTHER,
                        status="PASS", detail="No debarment record found.", source="mock_registry")
