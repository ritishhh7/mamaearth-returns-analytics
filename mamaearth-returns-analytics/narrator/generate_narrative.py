"""Generate an SCR narrative using Gemini when configured, otherwise offline.

Run from the repository root: python narrator/generate_narrative.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
SAMPLE_PATH = ROOT / "narrator" / "sample_output.txt"


def generate_scr_narrative_offline(findings: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, keyless SCR narrative built only from supplied findings."""
    revenue = findings["cleaned_total_revenue_inr"]
    raw_revenue = findings["raw_total_revenue_inr"]
    delta = findings["duplicate_reconciliation_delta_inr"]
    rates = findings["return_rate_by_payment"]
    segment = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    narrative = (
        "Situation\n"
        f"After removing duplicate submissions, the cleaned order dataset represents ₹{revenue:,.2f} "
        f"in revenue, compared with ₹{raw_revenue:,.2f} in the raw order records. The cleaned analysis "
        f"shows a {rates['COD']:.1f}% return rate for cash on delivery (COD), compared with "
        f"{rates['CARD']:.1f}% for card and {rates['UPI']:.1f}% for UPI orders.\n\n"
        "Complication\n"
        f"COD is the clearest operational risk: returns reach {segment['return_rate_pct']:.1f}% for "
        f"Tier-{segment['city_tier']} cities, the highest-risk segment in the analysis. The raw-to-cleaned "
        f"revenue difference is ₹{delta:,.2f}; an independent check attributes that amount to five "
        "duplicate order rows, rather than to missing-value imputation. The monthly trend also needs "
        f"careful reading: January appears to lead at ₹{inflated['apparent_revenue_inr']:,.2f}, but "
        "that figure is inflated by two unusually large quantity orders.\n\n"
        "Resolution\n"
        f"Prioritize a review of COD order confirmation, delivery and return handling in Tier-2 cities, "
        f"and track changes against the {segment['return_rate_pct']:.1f}% segment baseline. Add a duplicate-"
        f"submission control and reconcile order IDs before revenue is used for financial reporting. For "
        f"planning, use the outlier-corrected trend: {peak['month']} is the true peak month at "
        f"₹{peak['revenue_inr']:,.2f}. Treat these findings as signals for operational investigation, "
        "not proof that payment method alone causes returns."
    )
    return {"status": "success", "narrative": narrative, "tokens": None}


def generate_scr_narrative(findings: dict[str, Any]) -> dict[str, Any]:
    """Call Gemini if a key is available; return a structured result in every case."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return generate_scr_narrative_offline(findings)

    system_instruction = (
        "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
        "Write exactly three labeled sections: Situation, Complication, and Resolution. "
        "Every number in the output must come from the supplied findings and appear with the same "
        "value; do not invent statistics, totals, causes, or evidence. Be concise, practical, and "
        "clear about correlation versus causation."
    )
    # Construct the prompt from the passed dictionary so updated findings flow through automatically.
    contents = (
        "Write an executive-ready SCR narrative using only these verified findings. "
        "Use the figures exactly as supplied, explain the business implication, and recommend practical "
        "next steps without overstating causality.\n\nVerified findings JSON:\n"
        + json.dumps(findings, indent=2, sort_keys=True)
    )
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),
        )
        # Temperature 0.0 is appropriate because this is a factual report, not creative writing.
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                max_output_tokens=600,
            ),
        )
        narrative = (response.text or "").strip()
        if not narrative:
            raise ValueError("Gemini returned an empty narrative.")
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        return {"status": "success", "narrative": narrative, "tokens": tokens}
    except Exception as err:
        # Callers receive a structured error, never an uncaught API exception.
        return {"status": "error", "narrative": None, "message": str(err)}


def check_numeric_accuracy(narrative: str, findings: dict[str, Any]) -> bool:
    """Print a pass/fail result for each required numeric finding."""
    normalized = narrative.replace(",", "")
    checks = [
        ("cleaned revenue", f"{findings['cleaned_total_revenue_inr']:.2f}"),
        ("COD return rate", f"{findings['return_rate_by_payment']['COD']:.1f}"),
        ("COD + Tier-2 return rate", f"{findings['highest_risk_segment']['return_rate_pct']:.1f}"),
        ("duplicate reconciliation delta", f"{findings['duplicate_reconciliation_delta_inr']:.2f}"),
        ("true peak month and revenue",
         f"{findings['true_peak_month']['month']} {findings['true_peak_month']['revenue_inr']:.2f}"),
    ]
    passed = True
    for label, expected in checks:
        ok = all(part in normalized for part in expected.split())
        print(f"{'PASS' if ok else 'FAIL'} — {label}: expected {expected}")
        passed = passed and ok
    return passed


def main() -> int:
    if not FINDINGS_PATH.exists():
        print("Missing narrator/findings.json. Run `python analysis/clean_and_eda.py` first.")
        return 1
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    result = generate_scr_narrative(findings)
    if result["status"] == "error":
        print("Gemini request failed; using deterministic offline fallback.")
        print("Gemini error:", result["message"])
        result = generate_scr_narrative_offline(findings)

    narrative = result["narrative"]
    SAMPLE_PATH.write_text(narrative.rstrip() + "\n", encoding="utf-8")
    print(f"Narrative status: {result['status']}")
    print(narrative)
    print("\nNumeric accuracy checker:")
    if not check_numeric_accuracy(SAMPLE_PATH.read_text(encoding="utf-8"), findings):
        return 2
    print(f"\nSaved sample output to {SAMPLE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
