import json
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.models import (
    ComplianceReport,
    TenderComplianceReport,
)

from app.compliance_engine import (
    build_compliance_report,
    extract_uploaded_documents,
    evaluate_tender_requirements,
)

from app.tender_service import extract_tender_requirements


router = APIRouter()


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/health")
def health_check():
    return {"status": "ok"}


# ============================================================
# DOCUMENT EXTRACTION
# ============================================================

@router.post("/extract-documents")
async def extract_documents(
    pan_doc: Optional[UploadFile] = File(None),
    gst_doc: Optional[UploadFile] = File(None),
    udyam_doc: Optional[UploadFile] = File(None),
    epfo_doc: Optional[UploadFile] = File(None),
):
    """
    Upload bidder documents and use Gemini to extract
    registration numbers, entity names and dates.
    """

    uploads = {
        "PAN": pan_doc,
        "GST": gst_doc,
        "UDYAM": udyam_doc,
        "EPFO": epfo_doc,
    }

    files_payload = {}

    for doc_type, upload in uploads.items():

        if upload is not None:

            content = await upload.read()

            if not content:
                continue

            files_payload[doc_type] = (
                upload.filename,
                content,
                upload.content_type or "application/octet-stream",
            )

    if not files_payload:
        raise HTTPException(
            status_code=400,
            detail="No documents were uploaded.",
        )

    results = extract_uploaded_documents(
        files_payload
    )

    return {
        "extractions": results
    }


# ============================================================
# TENDER ANALYSIS
# ============================================================

@router.post("/analyze-tender")
async def analyze_tender(
    tender_doc: UploadFile = File(...)
):
    """
    Analyze a GeM tender document using Gemini
    and extract structured bidder requirements.
    """

    content = await tender_doc.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Tender document is empty.",
        )

    mime_type = (
        tender_doc.content_type
        or "application/pdf"
    )

    try:

        requirements = extract_tender_requirements(
            file_bytes=content,
            mime_type=mime_type,
        )

        return {
            "filename": tender_doc.filename,
            "analysis": requirements,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Tender analysis failed: {str(exc)}"
            ),
        )


# ============================================================
# NORMAL COMPLIANCE CHECK
# ============================================================

@router.post(
    "/verify-compliance",
    response_model=ComplianceReport,
)
async def verify_compliance(
    bidder_name: str = Form(...),
    gstin: Optional[str] = Form(None),
    pan: Optional[str] = Form(None),
    udyam_number: Optional[str] = Form(None),
    epfo_code: Optional[str] = Form(None),
    nsic_number: Optional[str] = Form(None),
):
    """
    Runs the standard compliance pipeline against
    the mock government registries.
    """

    if not bidder_name.strip():

        raise HTTPException(
            status_code=400,
            detail="bidder_name is required.",
        )

    report = build_compliance_report(
        bidder_name=bidder_name,
        gstin=gstin,
        pan=pan,
        udyam_number=udyam_number,
        epfo_code=epfo_code,
        nsic_number=nsic_number,
    )

    return report


# ============================================================
# TENDER-SPECIFIC COMPLIANCE CHECK
# ============================================================

@router.post(
    "/check-tender-compliance",
    response_model=TenderComplianceReport,
)
async def check_tender_compliance(
    bidder_name: str = Form(...),
    tender_title: str = Form(...),
    requirements_json: str = Form(...),

    gstin: Optional[str] = Form(None),
    pan: Optional[str] = Form(None),
    udyam_number: Optional[str] = Form(None),
    epfo_code: Optional[str] = Form(None),
    nsic_number: Optional[str] = Form(None),

    average_turnover: Optional[float] = Form(None),
    experience_years: Optional[float] = Form(None),
):
    """
    Compare a bidder against the requirements extracted
    from a specific GeM tender.
    """

    # --------------------------------------------------------
    # Validate bidder
    # --------------------------------------------------------

    if not bidder_name.strip():

        raise HTTPException(
            status_code=400,
            detail="bidder_name is required.",
        )

    # --------------------------------------------------------
    # Validate tender title
    # --------------------------------------------------------

    if not tender_title.strip():

        raise HTTPException(
            status_code=400,
            detail="tender_title is required.",
        )

    # --------------------------------------------------------
    # Validate requirements JSON
    # --------------------------------------------------------

    if not requirements_json.strip():

        raise HTTPException(
            status_code=400,
            detail="requirements_json is required.",
        )

    try:

        tender_analysis = json.loads(
            requirements_json
        )

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=400,
            detail=(
                "requirements_json must contain "
                "valid JSON."
            ),
        )

    # --------------------------------------------------------
    # Get extracted requirements
    # --------------------------------------------------------

    requirements = tender_analysis.get(
        "requirements",
        []
    )

    if not requirements:

        raise HTTPException(
            status_code=400,
            detail=(
                "No tender requirements were found "
                "in requirements_json."
            ),
        )

    # --------------------------------------------------------
    # Evaluate requirements
    # --------------------------------------------------------

    try:

        requirement_results = evaluate_tender_requirements(
            bidder_name=bidder_name,
            requirements=requirements,

            gstin=gstin,
            pan=pan,
            udyam_number=udyam_number,
            epfo_code=epfo_code,
            nsic_number=nsic_number,

            # IMPORTANT:
            # These two values are now passed
            # into the compliance engine.

            average_turnover=average_turnover,
            experience_years=experience_years,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Tender compliance evaluation failed: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # Calculate score
    # --------------------------------------------------------

    total = len(requirement_results)

    passed = sum(
        1
        for result in requirement_results
        if result["status"] == "PASS"
    )

    failed = sum(
        1
        for result in requirement_results
        if result["status"] == "FAIL"
    )

    if total > 0:

        score = round(
            (passed / total) * 100,
            1,
        )

    else:

        score = 0.0

    # --------------------------------------------------------
    # Determine overall status
    # --------------------------------------------------------

    if failed > 0:

        overall_status = "NOT_ELIGIBLE"

    elif any(
        result["status"] == "MANUAL_REVIEW"
        for result in requirement_results
    ):

        overall_status = "NEEDS_REVIEW"

    elif any(
        result["status"] == "WARNING"
        for result in requirement_results
    ):

        overall_status = "NEEDS_REVIEW"

    else:

        overall_status = "ELIGIBLE"

    # --------------------------------------------------------
    # Generate flags
    # --------------------------------------------------------

    flags = [
        (
            f"{result['title']}: "
            f"{result['reason']}"
        )
        for result in requirement_results
        if result["status"] in (
            "FAIL",
            "WARNING",
            "MANUAL_REVIEW",
        )
    ]

    # --------------------------------------------------------
    # Generate AI summary
    # --------------------------------------------------------

    try:

        from app.gemini_service import (
            generate_ai_summary
        )

        ai_summary = generate_ai_summary(
            bidder_name,
            requirement_results,
            score,
        )

    except Exception as exc:

        ai_summary = (
            "AI summary unavailable. "
            f"Overall status: {overall_status}, "
            f"score: {score}/100. "
            "Review flagged requirements manually. "
            f"Error: {exc}"
        )

    # --------------------------------------------------------
    # Return final report
    # --------------------------------------------------------

    return TenderComplianceReport(
        bidder_name=bidder_name,
        tender_title=tender_title,
        overall_status=overall_status,
        eligibility_score=score,
        requirements=requirement_results,
        ai_summary=ai_summary,
        flags=flags,
    )