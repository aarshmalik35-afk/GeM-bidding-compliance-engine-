# GeM Compliance Intelligence

> AI-assisted bid compliance verification for government procurement.

GeM Compliance Intelligence is a web-based prototype designed to assist procurement officers in reviewing bidder compliance against tender requirements.

The system combines AI-assisted document and tender understanding with deterministic, rule-based verification. Instead of relying on AI to make the final decision, the platform uses AI to extract and interpret relevant information and then applies backend compliance logic to evaluate the available data.

## 🚀 Live Demo

**[Open the Live Demo →](http://gem-compliance-frontend-aarsh.s3-website-us-east-1.amazonaws.com/)**

> This is a deployed prototype created for demonstration purposes.

---

## 📌 Problem

Bid evaluation can involve reviewing large amounts of tender information, bidder details, certificates, registrations, and supporting documents.

Important information may be distributed across different documents and may need to be manually compared against the requirements of a particular tender.

This creates a repetitive and time-consuming verification process.

The goal of this project is to provide a single interface that helps organize this process and highlight potential compliance issues before the final decision is made by the procurement officer.

---

## 💡 Solution

The platform provides a structured workflow for bid compliance verification:

1. Enter bidder information
2. Upload or provide relevant documents
3. Analyze tender requirements
4. Use AI to understand and extract relevant information
5. Apply deterministic compliance rules
6. Generate compliance results and flags
7. Present the results through an officer-facing dashboard

The system is designed as **decision support**, not as an autonomous tender awarding or rejection system.

### Core approach

```text
Unstructured Documents
        │
        ▼
AI-assisted Understanding
        │
        ▼
Structured Information
        │
        ▼
Rule-based Verification
        │
        ▼
Compliance Results
        │
        ▼
Officer Review
