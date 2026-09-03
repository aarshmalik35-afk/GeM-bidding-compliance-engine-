"""
Gemini integration layer.

Uses Google's current google-genai Python SDK.

Two jobs:
1. extract_document_fields()
   Reads an uploaded document and extracts structured bidder information.

2. generate_ai_summary()
   Generates a concise procurement-officer summary from compliance results.
"""

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

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------
# JSON helper
# ---------------------------------------------------------

def _extract_json_block(text: str) -> dict:
    """
    Safely extract JSON from Gemini's response.

    Handles:
    - normal JSON
    - ```json ... ``` responses
    - JSON surrounded by additional text
    """

    if not text:
        raise ValueError("Gemini returned an empty response.")

    cleaned = text.strip()

    # Remove markdown fences
    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^```\s*",
        "",
        cleaned,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    # Try direct JSON parsing first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting the outermost JSON object
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
# Document extraction
# ---------------------------------------------------------

def extract_document_fields(
    file_bytes: bytes,
    mime_type: str,
    doc_type_hint: str,
) -> dict:
    """
    Send an uploaded document to Gemini and extract
    important bidder fields.

    Supports images and PDFs.
    """

    if not file_bytes:
        raise ValueError("Uploaded document is empty.")

    prompt = f"""
You are an assistant helping a government procurement
officer verify bidder documents for a GeM tender.

The uploaded document is expected to be:

{doc_type_hint}

Carefully inspect the document.

Extract the following information:

1. Document type
2. Primary registration / identification number
3. Entity / company name
4. Issue date or validity date if visible
5. Extraction confidence

IMPORTANT:

- Do not invent information.
- If a field cannot be read, return null.
- Preserve registration numbers exactly.
- If the document contains multiple numbers, select
  the primary number relevant to the document.
- Confidence should reflect how clearly the document
  supports the extracted values.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "document_type": "PAN",
    "registration_number": null,
    "entity_name": null,
    "validity_or_date": null,
    "confidence": "high"
}}

Allowed document_type values:

PAN
GST
UDYAM
EPFO
ESIC
NSIC
STARTUP_INDIA
OEM_AUTHORIZATION
OTHER

Allowed confidence values:

high
medium
low
"""

    # Create a Gemini Part directly from the uploaded bytes.
    document_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                document_part,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

    except Exception as exc:
        raise RuntimeError(
            f"Gemini document extraction failed: {exc}"
        ) from exc

    return _extract_json_block(response.text)


# ---------------------------------------------------------
# AI compliance summary
# ---------------------------------------------------------

def generate_ai_summary(
    bidder_name: str,
    checks: list,
    score: float
) -> str:

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    prompt = f"""
You are an expert government procurement compliance analyst.

Generate a concise compliance assessment for this bidder.

Bidder:
{bidder_name}

Eligibility score:
{score}/100

Compliance checks:
{json.dumps(checks, indent=2)}

Write a professional summary for a procurement officer.

Include:
1. Overall compliance status
2. Important checks that passed
3. Any failed or warning checks
4. Whether the bidder appears eligible
5. Any issues that should be manually reviewed

Do not invent facts.
Only use the information provided above.

Keep the response concise, around 100-150 words.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        return response.text.strip()

    except Exception as exc:
        raise RuntimeError(
            f"Gemini AI summary generation failed: {exc}"
        ) from exc