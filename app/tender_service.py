"""
Gemini tender analysis integration.

Extracts bidder eligibility, compliance, and qualification
requirements from an uploaded GeM tender PDF using Google's
google-genai Python SDK.
"""

import json
import random
import re
import time

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL


# ---------------------------------------------------------
# Gemini client
# ---------------------------------------------------------

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured. "
        "Check your environment variables."
    )

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------
# Gemini retry helper
# ---------------------------------------------------------

def _is_retryable_error(exc: Exception) -> bool:
    """Return True for temporary overload, rate-limit, and server errors."""
    message = str(exc).lower()
    code = getattr(exc, "code", None)
    status_code = getattr(exc, "status_code", None)

    if code in (429, 500, 502, 503, 504) or status_code in (
        429, 500, 502, 503, 504
    ):
        return True

    retryable_markers = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "resource_exhausted",
        "unavailable",
        "internal server error",
        "deadline exceeded",
        "timed out",
        "timeout",
        "service unavailable",
        "high demand",
    )
    return any(marker in message for marker in retryable_markers)


def _generate_with_retry(
    *,
    model: str,
    contents,
    config,
    max_attempts: int = 4,
):
    """
    Retry transient Gemini failures with exponential backoff.
    Waits roughly 1, 2, then 4 seconds plus small jitter.
    """
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            if not _is_retryable_error(exc) or attempt == max_attempts - 1:
                raise

            delay = min(2 ** attempt, 8) + random.uniform(0, 0.5)
            print(
                "Temporary Gemini error during tender analysis "
                f"(attempt {attempt + 1}/{max_attempts}). "
                f"Retrying in {delay:.1f} seconds. Error: {exc}"
            )
            time.sleep(delay)

    # Defensive guard; the loop either returns or raises.
    raise RuntimeError("Gemini request failed after all retry attempts.")


# ---------------------------------------------------------
# JSON helper
# ---------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract a JSON object from Gemini's response."""
    if not text:
        raise ValueError("Gemini returned an empty response.")

    cleaned = text.strip()
    cleaned = re.sub(
        r"^```json\s*", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError("Gemini JSON response must be an object.")
        return result
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Gemini returned invalid JSON: {cleaned[:500]}"
    )


# ---------------------------------------------------------
# Tender requirement extraction
# ---------------------------------------------------------

def extract_tender_requirements(
    file_bytes: bytes,
    mime_type: str,
) -> dict:
    """
    Analyze a GeM tender document and return structured requirements.
    """
    if not file_bytes:
        raise ValueError("Tender document is empty.")

    prompt = """
You are an expert government procurement compliance analyst.

Analyze the uploaded GeM tender document. Identify bidder eligibility,
compliance, and qualification requirements that must be verified before
accepting the bid.

Look for:
- GST requirements
- PAN / Income Tax requirements
- Udyam / MSME requirements
- EPFO / ESIC requirements
- NSIC requirements
- Startup India requirements
- OEM authorization
- minimum or average turnover
- financial capacity
- prior experience and minimum years of experience
- mandatory certificates and declarations
- technical eligibility
- registration and validity requirements
- blacklisting / debarment conditions
- any other bidder eligibility condition

Only extract requirements actually present in the tender. Do not invent
requirements. For each requirement, include:
- requirement_id (for example REQ-001)
- title
- category
- description
- mandatory (boolean)
- verification_type
- threshold (number or null)
- threshold_operator (string or null)
- unit (string or null)
- period (string or null)
- required_evidence (array)
- source_text (supporting text from the tender)

Allowed category values:
FINANCIAL, REGISTRATION, EXPERIENCE, MANDATORY_DOCUMENT,
DECLARATION, TECHNICAL, OTHER

Allowed verification_type values:
DOCUMENT_PRESENCE, EXACT_MATCH, THRESHOLD, DATE_VALIDITY,
ENTITY_MATCH, MANUAL_REVIEW

For numerical requirements, extract the threshold, comparison operator,
unit, and applicable period when present. For example, "average annual
turnover should be at least Rs. 10 Crore during the last three financial
years" should have threshold 10, threshold_operator ">=", unit
"INR_CRORE", and period "LAST_3_FINANCIAL_YEARS".

Return ONLY valid JSON using exactly this top-level structure:
{
  "tender_title": "...",
  "tender_reference": null,
  "requirements": []
}
"""

    tender_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )

    try:
        response = _generate_with_retry(
            model=GEMINI_MODEL,
            contents=[prompt, tender_part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
            max_attempts=4,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Gemini tender analysis failed after retry handling: {exc}"
        ) from exc

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    result = _extract_json(response.text)

    if "requirements" not in result:
        raise ValueError(
            "Gemini response does not contain 'requirements'."
        )

    if not isinstance(result["requirements"], list):
        raise ValueError(
            "Gemini response field 'requirements' must be a list."
        )

    return result
