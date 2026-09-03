import json
import re

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL


# ---------------------------------------------------------
# Gemini client
# ---------------------------------------------------------

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured. "
        "Check your .env file."
    )

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ---------------------------------------------------------
# JSON helper
# ---------------------------------------------------------

def _extract_json(text: str) -> dict:
    """
    Safely extract a JSON object from Gemini's response.

    Handles:
    - normal JSON
    - ```json fenced responses
    - extra text surrounding the JSON
    """

    if not text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    cleaned = text.strip()

    # Remove markdown code fences
    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"^```\s*",
        "",
        cleaned
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    # Try parsing the complete response
    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        pass

    # Gemini may sometimes add text before/after JSON.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:

        json_text = cleaned[start:end + 1]

        try:
            return json.loads(json_text)

        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Gemini returned invalid JSON: {cleaned[:500]}"
    )


# ---------------------------------------------------------
# TENDER REQUIREMENT EXTRACTION
# ---------------------------------------------------------

def extract_tender_requirements(
    file_bytes: bytes,
    mime_type: str
) -> dict:
    """
    Analyze a GeM tender document using Gemini and extract
    bidder eligibility and compliance requirements.
    """

    if not file_bytes:
        raise ValueError(
            "Tender document is empty."
        )

    prompt = """
You are an expert government procurement
compliance analyst.

Analyze the uploaded GeM tender document.

Your task is to identify the bidder eligibility,
compliance and qualification requirements that
must be verified before accepting the bid.

Look specifically for:

- GST requirements
- PAN / Income Tax requirements
- Udyam / MSME requirements
- EPFO / ESIC requirements
- NSIC requirements
- Startup India requirements
- OEM authorization
- minimum turnover
- average turnover
- financial capacity
- prior experience
- minimum years of experience
- mandatory certificates
- declarations
- technical eligibility
- registration requirements
- validity requirements
- blacklisting / debarment conditions
- any other bidder eligibility condition

IMPORTANT:

Only extract requirements that are actually present
in the tender document.

DO NOT invent requirements.

For every requirement return:

{
    "requirement_id": "REQ-001",
    "title": "...",
    "category": "...",
    "description": "...",
    "mandatory": true,
    "verification_type": "...",
    "threshold": null,
    "threshold_operator": null,
    "unit": null,
    "period": null,
    "required_evidence": [],
    "source_text": "..."
}

Possible category values:

FINANCIAL
REGISTRATION
EXPERIENCE
MANDATORY_DOCUMENT
DECLARATION
TECHNICAL
OTHER

Possible verification_type values:

DOCUMENT_PRESENCE
EXACT_MATCH
THRESHOLD
DATE_VALIDITY
ENTITY_MATCH
MANUAL_REVIEW

For numerical requirements:

- Extract the numerical threshold.
- Extract the comparison operator.
- Extract the unit.
- Extract the applicable period.

Example:

If the tender says:

"Average annual turnover should be at least
Rs. 10 Crore during the last three financial years."

Return:

{
    "threshold": 10,
    "threshold_operator": ">=",
    "unit": "INR_CRORE",
    "period": "LAST_3_FINANCIAL_YEARS"
}

Return ONLY valid JSON.

Use exactly this top-level structure:

{
    "tender_title": "...",
    "tender_reference": null,
    "requirements": []
}
"""

    # -----------------------------------------------------
    # Convert uploaded bytes into a Gemini document part
    # -----------------------------------------------------

    tender_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type
    )

    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                tender_part
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0
            )
        )

    except Exception as exc:

        raise RuntimeError(
            f"Gemini tender analysis failed: {exc}"
        ) from exc

    # -----------------------------------------------------
    # Validate response
    # -----------------------------------------------------

    if not response.text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    result = _extract_json(
        response.text
    )

    if "requirements" not in result:
        raise ValueError(
            "Gemini response does not contain "
            "'requirements'."
        )

    return result