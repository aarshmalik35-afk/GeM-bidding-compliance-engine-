import uuid
from typing import Dict, List, Optional

from app.models import CheckResult, ComplianceReport, DocType
from app import mock_registry
from app.gemini_service import extract_document_fields, generate_ai_summary

# Weight given to each check when computing the overall eligibility score.
# Mandatory checks (GST, PAN, debarment) weigh more than optional ones.
CHECK_WEIGHTS = {
    "GST Registration": 25,
    "PAN / Income Tax": 25,
    "Blacklisting / Debarment": 25,
    "Udyam / MSME Registration": 10,
    "EPFO Compliance": 10,
    "NSIC Registration": 5,
}

STATUS_SCORE = {
    "PASS": 1.0,
    "WARNING": 0.5,
    "NOT_PROVIDED": 0.5,   # optional docs not submitted shouldn't fully tank the score
    "FAIL": 0.0,
}


def extract_uploaded_documents(files: Dict[str, tuple]) -> List[dict]:
    """
    files: dict of { doc_type_hint: (filename, file_bytes, mime_type) }
    Returns a list of Gemini extraction results, one per document.
    """
    results = []
    for doc_type_hint, (filename, file_bytes, mime_type) in files.items():
        try:
            extracted = extract_document_fields(file_bytes, mime_type, doc_type_hint)
        except Exception as exc:  # keep the demo alive even if one call fails
            extracted = {"error": str(exc)}
        extracted["_filename"] = filename
        extracted["_doc_type_hint"] = doc_type_hint
        results.append(extracted)
    return results


def run_compliance_checks(
    bidder_name: str,
    gstin: Optional[str],
    pan: Optional[str],
    udyam_number: Optional[str],
    epfo_code: Optional[str],
    nsic_number: Optional[str],
) -> List[CheckResult]:
    return [
        mock_registry.check_gst(gstin),
        mock_registry.check_pan(pan),
        mock_registry.check_udyam(udyam_number),
        mock_registry.check_epfo(epfo_code),
        mock_registry.check_nsic(nsic_number),
        mock_registry.check_debarment(bidder_name),
    ]


def compute_score(checks: List[CheckResult]) -> float:
    total_weight = sum(CHECK_WEIGHTS.get(c.check_name, 0) for c in checks) or 1
    earned = sum(
        CHECK_WEIGHTS.get(c.check_name, 0) * STATUS_SCORE.get(c.status, 0)
        for c in checks
    )
    return round((earned / total_weight) * 100, 1)


def determine_overall_status(checks: List[CheckResult], score: float) -> str:
    if any(c.status == "FAIL" and CHECK_WEIGHTS.get(c.check_name, 0) >= 25 for c in checks):
        return "NOT_ELIGIBLE"
    if score >= 85:
        return "ELIGIBLE"
    return "NEEDS_REVIEW"


def build_compliance_report(
    bidder_name: str,
    gstin: Optional[str] = None,
    pan: Optional[str] = None,
    udyam_number: Optional[str] = None,
    epfo_code: Optional[str] = None,
    nsic_number: Optional[str] = None,
) -> ComplianceReport:
    checks = run_compliance_checks(bidder_name, gstin, pan, udyam_number, epfo_code, nsic_number)
    score = compute_score(checks)
    overall_status = determine_overall_status(checks, score)

    flags = [f"{c.check_name}: {c.detail}" for c in checks if c.status in ("FAIL", "WARNING")]

    checks_summary = [c.model_dump() for c in checks]
    try:
        ai_summary = generate_ai_summary(bidder_name, checks_summary, score)
    except Exception as exc:
        ai_summary = (
            f"[AI summary unavailable: {exc}] Overall status: {overall_status}, "
            f"score: {score}/100. Review flagged checks manually."
        )

    return ComplianceReport(
        bidder_name=bidder_name,
        bidder_id=str(uuid.uuid4())[:8],
        overall_status=overall_status,
        eligibility_score=score,
        checks=checks,
        ai_summary=ai_summary,
        flags=flags,
    )
def evaluate_tender_requirements(
    bidder_name: str,
    requirements: List[dict],
    gstin: Optional[str] = None,
    pan: Optional[str] = None,
    udyam_number: Optional[str] = None,
    epfo_code: Optional[str] = None,
    nsic_number: Optional[str] = None,
    average_turnover: Optional[float] = None,
    experience_years: Optional[float] = None,
) -> List[dict]:

    # --------------------------------------------------------
    # Run existing registry checks
    # --------------------------------------------------------

    checks = run_compliance_checks(
        bidder_name=bidder_name,
        gstin=gstin,
        pan=pan,
        udyam_number=udyam_number,
        epfo_code=epfo_code,
        nsic_number=nsic_number,
    )

    # Convert checks into lookup dictionary
    check_lookup = {
        check.check_name.lower(): check
        for check in checks
    }

    results = []

    # --------------------------------------------------------
    # Helper for numerical comparisons
    # --------------------------------------------------------

    def compare_values(
        bidder_value: float,
        required_value: float,
        operator: str,
    ):
        if operator == ">=":
            return bidder_value >= required_value

        elif operator == ">":
            return bidder_value > required_value

        elif operator == "<=":
            return bidder_value <= required_value

        elif operator == "<":
            return bidder_value < required_value

        elif operator in ("=", "=="):
            return bidder_value == required_value

        return None

    # --------------------------------------------------------
    # Evaluate every tender requirement
    # --------------------------------------------------------

    for requirement in requirements:

        requirement_id = requirement.get(
            "requirement_id",
            "UNKNOWN",
        )

        title = requirement.get(
            "title",
            "Unknown requirement",
        )

        category = requirement.get(
            "category",
            "OTHER",
        )

        title_lower = title.lower()

        status = "MANUAL_REVIEW"
        reason = (
            "This requirement was extracted from the tender "
            "but automatic verification is not implemented yet. "
            "Procurement officer review is required."
        )

        # ====================================================
        # 1. GST
        # ====================================================

        if "gst" in title_lower:

            matched_check = check_lookup.get(
                "gst registration"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 2. PAN / Income Tax
        # ====================================================

        elif (
            "pan" in title_lower
            or "income tax" in title_lower
        ):

            matched_check = check_lookup.get(
                "pan / income tax"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 3. UDYAM / MSME
        # ====================================================

        elif (
            "udyam" in title_lower
            or "msme" in title_lower
        ):

            matched_check = check_lookup.get(
                "udyam / msme registration"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 4. EPFO
        # ====================================================

        elif "epfo" in title_lower:

            matched_check = check_lookup.get(
                "epfo compliance"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 5. NSIC
        # ====================================================

        elif "nsic" in title_lower:

            matched_check = check_lookup.get(
                "nsic registration"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 6. BLACKLISTING / DEBARMENT
        # ====================================================

        elif (
            "blacklist" in title_lower
            or "debar" in title_lower
        ):

            matched_check = check_lookup.get(
                "blacklisting / debarment"
            )

            if matched_check:

                if matched_check.status == "PASS":
                    status = "PASS"

                elif matched_check.status == "FAIL":
                    status = "FAIL"

                elif matched_check.status == "WARNING":
                    status = "WARNING"

                else:
                    status = "NOT_PROVIDED"

                reason = matched_check.detail

        # ====================================================
        # 7. AVERAGE TURNOVER
        # ====================================================

        elif "turnover" in title_lower:

            threshold = requirement.get(
                "threshold"
            )

            operator = requirement.get(
                "threshold_operator",
                ">=",
            )

            unit = requirement.get(
                "unit"
            )

            # Bidder did not provide turnover
            if average_turnover is None:

                status = "NOT_PROVIDED"

                reason = (
                    "Tender requires a minimum turnover, "
                    "but bidder average turnover was not provided."
                )

            # Tender did not provide numerical threshold
            elif threshold is None:

                status = "MANUAL_REVIEW"

                reason = (
                    "Turnover requirement was detected, "
                    "but no numerical threshold was extracted "
                    "from the tender."
                )

            else:

                try:

                    bidder_value = float(
                        average_turnover
                    )

                    required_value = float(
                        threshold
                    )

                    passed = compare_values(
                        bidder_value,
                        required_value,
                        operator,
                    )

                    if passed is None:

                        status = "MANUAL_REVIEW"

                        reason = (
                            f"Unsupported turnover comparison "
                            f"operator: {operator}"
                        )

                    elif passed:

                        status = "PASS"

                        reason = (
                            f"Bidder average turnover "
                            f"{bidder_value} {unit or ''} "
                            f"meets the tender requirement "
                            f"{operator} {required_value} "
                            f"{unit or ''}."
                        )

                    else:

                        status = "FAIL"

                        reason = (
                            f"Bidder average turnover "
                            f"{bidder_value} {unit or ''} "
                            f"does not meet the tender requirement "
                            f"{operator} {required_value} "
                            f"{unit or ''}."
                        )

                except (TypeError, ValueError):

                    status = "MANUAL_REVIEW"

                    reason = (
                        "Bidder turnover data could not "
                        "be interpreted as a number."
                    )

        # ====================================================
        # 8. EXPERIENCE / YEARS OF EXPERIENCE
        # ====================================================

        elif (
            "experience" in title_lower
            or "years of experience" in title_lower
            or "prior experience" in title_lower
        ):

            threshold = requirement.get(
                "threshold"
            )

            operator = requirement.get(
                "threshold_operator",
                ">=",
            )

            # Bidder did not provide experience
            if experience_years is None:

                status = "NOT_PROVIDED"

                reason = (
                    "Tender requires prior experience, "
                    "but bidder experience was not provided."
                )

            # Tender threshold missing
            elif threshold is None:

                status = "MANUAL_REVIEW"

                reason = (
                    "Experience requirement was extracted, "
                    "but no numerical experience threshold "
                    "was identified."
                )

            else:

                try:

                    bidder_value = float(
                        experience_years
                    )

                    required_value = float(
                        threshold
                    )

                    passed = compare_values(
                        bidder_value,
                        required_value,
                        operator,
                    )

                    if passed is None:

                        status = "MANUAL_REVIEW"

                        reason = (
                            f"Unsupported experience comparison "
                            f"operator: {operator}"
                        )

                    elif passed:

                        status = "PASS"

                        reason = (
                            f"Bidder experience of "
                            f"{bidder_value} years meets "
                            f"the tender requirement "
                            f"{operator} {required_value} years."
                        )

                    else:

                        status = "FAIL"

                        reason = (
                            f"Bidder experience of "
                            f"{bidder_value} years does not meet "
                            f"the tender requirement "
                            f"{operator} {required_value} years."
                        )

                except (TypeError, ValueError):

                    status = "MANUAL_REVIEW"

                    reason = (
                        "Bidder experience data could not "
                        "be interpreted as a number."
                    )

        # ====================================================
        # 9. EVERYTHING ELSE
        # ====================================================

        else:

            status = "MANUAL_REVIEW"

            reason = (
                "This requirement was extracted from the tender "
                "but automatic verification is not implemented yet. "
                "Procurement officer review is required."
            )

        # ====================================================
        # Store result
        # ====================================================

        results.append(
            {
                "requirement_id": requirement_id,
                "title": title,
                "category": category,
                "status": status,
                "reason": reason,
            }
        )

    return results