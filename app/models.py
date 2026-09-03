from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class DocType(str, Enum):
    PAN = "PAN"
    GST = "GST"
    UDYAM = "UDYAM"          # MSME registration
    EPFO = "EPFO"
    ESIC = "ESIC"
    NSIC = "NSIC"
    STARTUP_INDIA = "STARTUP_INDIA"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    OTHER = "OTHER"


class ExtractedDocument(BaseModel):
    doc_type: DocType
    filename: str
    extracted_number: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_validity: Optional[str] = None
    raw_extraction: dict = {}
    extraction_confidence: Optional[str] = None  # "high" | "medium" | "low"


class CheckResult(BaseModel):
    check_name: str
    doc_type: DocType
    status: str            # "PASS" | "FAIL" | "WARNING" | "NOT_PROVIDED"
    detail: str
    source: str             # "mock_registry" (swap for live API in production)


class ComplianceReport(BaseModel):
    bidder_name: str
    bidder_id: str
    overall_status: str     # "ELIGIBLE" | "NOT_ELIGIBLE" | "NEEDS_REVIEW"
    eligibility_score: float  # 0-100
    checks: List[CheckResult]
    ai_summary: str
    flags: List[str] = []

class TenderRequirementResult(BaseModel):
    requirement_id: str
    title: str
    category: str
    status: str
    reason: str


class TenderComplianceReport(BaseModel):
    bidder_name: str
    tender_title: str
    overall_status: str
    eligibility_score: float
    requirements: List[TenderRequirementResult]
    ai_summary: str
    flags: List[str] = []