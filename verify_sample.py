"""
Verification pass for the research agent's output (v3 - Tavily + Groq).

WHAT THIS DOES:
Takes a random sample of the agent's results (default 20 apps) and re-checks
each one with a SECOND, independent search + extraction pass - a fresh Tavily
search plus a Groq call explicitly told to be skeptical and look for mistakes
in the first pass.

HOW TO RUN:
    python verify_sample.py
Output: output/verification_report.json
"""

import json
import os
import random
import time
from groq import Groq
from tavily import TavilyClient

GROQ_KEY = os.environ.get("GROQ_API_KEY")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY")

if not GROQ_KEY:
    raise SystemExit("Set GROQ_API_KEY as an environment variable before running.")
if not TAVILY_KEY:
    raise SystemExit("Set TAVILY_API_KEY as an environment variable before running.")

groq = Groq(api_key=GROQ_KEY)
tavily = TavilyClient(api_key=TAVILY_KEY)

MODEL = "openai/gpt-oss-20b"
SAMPLE_SIZE = 20
random.seed(42)

VERIFY_SYSTEM_PROMPT = """You are a skeptical auditor checking another AI agent's research.
You will be given an app name, that agent's claimed findings, and a FRESH set of search results
gathered independently. Check whether the original claim holds up against this fresh evidence.

Respond with ONLY a valid JSON object, nothing else, in this shape:
{
  "agrees_with_original": true or false,
  "disagreement_field": "which field, if any, you disagree on, or empty string",
  "your_finding": "your own independent finding on that field, or empty string if you agree",
  "evidence_url": "the URL from the fresh search results you used",
  "confidence": "high" or "medium" or "low"
}
"""


def fresh_search(app_name: str) -> list:
    query = f"{app_name} API documentation authentication developer"
    try:
        result = tavily.search(query=query, search_depth="advanced", max_results=4)
        return result.get("results", [])
    except Exception:
        return []


def verify_one(original: dict) -> dict:
    claim_summary = {
        "auth_methods": original.get("auth_methods"),
        "self_serve": original.get("self_serve"),
        "api_surface": original.get("api_surface"),
        "buildability_verdict": original.get("buildability_verdict"),
    }

    fresh_results = fresh_search(original["_app_name"])
    if not fresh_results:
        return {
            "_app_id": original["_app_id"],
            "_app_name": original["_app_name"],
            "_status": "verification_search_failed",
        }

    context_lines = []
    for r in fresh_results:
        context_lines.append(f"URL: {r.get('url', 'unknown')}")
        context_lines.append(f"Content: {r.get('content', '')[:1200]}")
        context_lines.append("---")
    context = "\n".join(context_lines)

    user_prompt = f"""App: {original['_app_name']}
Original agent's claim: {json.dumps(claim_summary)}
Original evidence URL cited: {original.get('evidence_url', 'none given')}

Fresh, independently gathered search results:
{context}

Does the original claim hold up against this fresh evidence?"""

    try:
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content.strip()

        verification = json.loads(raw_text)
        verification["_app_id"] = original["_app_id"]
        verification["_app_name"] = original["_app_name"]
        verification["_status"] = "ok"
        return verification

    except Exception as e:
        return {
            "_app_id": original["_app_id"],
            "_app_name": original["_app_name"],
            "_status": "verification_failed",
            "_error": str(e),
        }


def main():
    os.makedirs("output", exist_ok=True)

    with open("output/research_raw.json") as f:
        all_results = json.load(f)

    ok_results = [r for r in all_results if r.get("_status") == "ok"]
    sample = random.sample(ok_results, min(SAMPLE_SIZE, len(ok_results)))

    print(f"Verifying a random sample of {len(sample)} apps...\n")

    verifications = []
    for i, original in enumerate(sample, 1):
        print(f"[{i}/{len(sample)}] Re-checking {original['_app_name']}...", end=" ", flush=True)
        v = verify_one(original)
        verifications.append(v)
        status = v.get("_status", "unknown")
        agree = "AGREES" if v.get("agrees_with_original") else "DISAGREES/UNCLEAR"
        print(status, "-", agree if status == "ok" else "")
        time.sleep(0.5)

    agreements = sum(1 for v in verifications if v.get("agrees_with_original") is True)
    disagreements = sum(1 for v in verifications if v.get("agrees_with_original") is False)
    failed = sum(1 for v in verifications if v.get("_status") != "ok")

    summary = {
        "sample_size": len(sample),
        "agreements": agreements,
        "disagreements": disagreements,
        "verification_call_failures": failed,
        "first_pass_accuracy_estimate": f"{round(agreements / len(sample) * 100, 1)}%" if sample else "n/a",
        "details": verifications,
    }

    with open("output/verification_report.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{agreements}/{len(sample)} agreed with the original research.")
    print(f"Estimated first-pass accuracy on this sample: {summary['first_pass_accuracy_estimate']}")
    print("Full report saved to output/verification_report.json")


if __name__ == "__main__":
    main()
