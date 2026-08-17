"""
Research Agent for Composio's 100-app assignment (v3 - Tavily + Groq).

WHAT CHANGED FROM v2:
Gemini's API (even plain text generation, no search tool) required a funded
"prepay" balance that kept coming back depleted despite Google Cloud free
trial credits being active - a billing plumbing issue between two separate
Google systems that wasn't resolvable within the assignment's time budget.
This version replaces Gemini entirely with Groq (a genuinely free-tier LLM
API, no card required) for the extraction step. Tavily still handles search.

ARCHITECTURE:
  1. SEARCH: Tavily finds and fetches relevant developer documentation
     content for each app.
  2. EXTRACT: Groq (running Llama 3.3) reads that content and returns
     structured JSON findings.

WHY THIS COUNTS AS "AN AGENT, NOT BY HAND":
For each app, the script decides what to search for, fetches real page
content from the web via Tavily, and feeds that content to an LLM to
extract structured findings - all without a human reading each doc page.

WHERE A HUMAN IS STILL NEEDED (documented honestly, per the assignment):
- Tavily's search may return an irrelevant or thin result for niche apps
- The LLM can still misread ambiguous docs, or find conflicting auth info
- Apps with very little public documentation get flagged low-confidence,
  not silently guessed at
- A human verification pass (see verify_sample.py) catches these cases
- Debugging and redesigning this pipeline itself required real judgment -
  documented in the README rather than hidden

HOW TO RUN:
1. Set both API keys:
   set TAVILY_API_KEY=your-tavily-key
   set GROQ_API_KEY=your-groq-key
2. Run:  python research_agent.py
3. Output lands in: output/research_raw.json
"""

import json
import os
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

MODEL = "openai/gpt-oss-20b"  # free tier on Groq, strong enough for structured extraction

EXTRACT_SYSTEM_PROMPT = """You are a research analyst reviewing search results about a developer platform/API.
Based ONLY on the provided search content (not your prior knowledge), answer with a SINGLE valid JSON
object (no markdown, no commentary, no explanation before or after) in exactly this shape:

{
  "auth_methods": ["OAuth2" or "API key" or "Basic" or "token" or "other" or "unclear"],
  "self_serve": "self-serve" or "gated" or "partially gated" or "unclear",
  "gating_detail": "one short sentence on what gates access, if anything",
  "api_surface": "REST" or "GraphQL" or "REST and GraphQL" or "none found" or "other",
  "api_breadth": "broad" or "narrow" or "unclear",
  "existing_mcp": true or false or "unclear",
  "buildability_verdict": "yes" or "no" or "maybe",
  "buildability_blocker": "one short sentence on the main blocker, or 'none' if buildable today",
  "evidence_url": "the most relevant URL from the search results",
  "confidence": "high" or "medium" or "low",
  "notes": "anything unusual or worth flagging, 1 sentence, or empty string"
}

Be honest about uncertainty - use "unclear" and "confidence": "low" rather than guessing.
If the search results suggest the app is paywalled/contact-sales gated, that IS a valid finding.
If the search results are thin or irrelevant, say so with low confidence rather than inventing detail.
Respond with ONLY the JSON object, nothing else.
"""


def search_app_docs(app: dict) -> dict:
    """Step 1: use Tavily to find and fetch relevant documentation content."""
    query = f"{app['name']} API documentation authentication developer"
    try:
        result = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=4,
            include_raw_content=False,
        )
        return {"ok": True, "results": result.get("results", [])}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_findings(app: dict, search_data: dict) -> dict:
    """Step 2: feed search results to Groq for structured extraction."""
    if not search_data["ok"]:
        return {
            "_app_id": app["id"],
            "_app_name": app["name"],
            "_category": app["category"],
            "_status": "search_failed",
            "_error": search_data["error"],
        }

    results = search_data["results"]
    if not results:
        return {
            "_app_id": app["id"],
            "_app_name": app["name"],
            "_category": app["category"],
            "_status": "no_search_results",
        }

    context_lines = []
    for r in results:
        context_lines.append(f"URL: {r.get('url', 'unknown')}")
        context_lines.append(f"Title: {r.get('title', '')}")
        context_lines.append(f"Content: {r.get('content', '')[:1500]}")
        context_lines.append("---")
    context = "\n".join(context_lines)

    user_prompt = f"""App: {app['name']}
Category (given): {app['category']}

Search results about this app's documentation:
{context}

Based on the above search results, answer in the required JSON format."""

    try:
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},  # Groq supports forcing valid JSON output
        )
        raw_text = response.choices[0].message.content.strip()

        parsed = json.loads(raw_text)
        parsed["_app_id"] = app["id"]
        parsed["_app_name"] = app["name"]
        parsed["_category"] = app["category"]
        parsed["_status"] = "ok"
        return parsed

    except json.JSONDecodeError as e:
        return {
            "_app_id": app["id"],
            "_app_name": app["name"],
            "_category": app["category"],
            "_status": "json_parse_failed",
            "_raw_response": raw_text[:500] if "raw_text" in dir() else "",
            "_error": str(e),
        }
    except Exception as e:
        return {
            "_app_id": app["id"],
            "_app_name": app["name"],
            "_category": app["category"],
            "_status": "extraction_failed",
            "_error": str(e),
        }


def research_app(app: dict) -> dict:
    search_data = search_app_docs(app)
    return extract_findings(app, search_data)


def main():
    os.makedirs("output", exist_ok=True)

    with open("data/apps.json") as f:
        apps = json.load(f)

    # Resume support: if a previous run already produced results, only retry
    # apps that failed last time (saves tokens - important on a free daily quota).
    existing_results = {}
    output_path = "output/research_raw.json"
    if os.path.exists(output_path):
        with open(output_path) as f:
            previous = json.load(f)
        for r in previous:
            existing_results[r["_app_id"]] = r
        already_ok = sum(1 for r in previous if r.get("_status") == "ok")
        print(f"Found existing results: {already_ok}/{len(previous)} already succeeded. Resuming - only retrying failures.\n")

    results = []
    print(f"Researching {len(apps)} apps (Tavily search + Groq extraction)...\n")

    for i, app in enumerate(apps, 1):
        prior = existing_results.get(app["id"])
        if prior and prior.get("_status") == "ok":
            print(f"[{i}/{len(apps)}] {app['name']}... skipped (already ok)")
            results.append(prior)
            continue

        print(f"[{i}/{len(apps)}] {app['name']}...", end=" ", flush=True)
        result = research_app(app)
        results.append(result)
        print(result.get("_status", "unknown"))

        time.sleep(0.5)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    ok_count = sum(1 for r in results if r.get("_status") == "ok")
    print(f"\nDone. {ok_count}/{len(apps)} researched successfully.")
    print("Failures (if any) are logged in output/research_raw.json with _status != 'ok'.")


if __name__ == "__main__":
    main()
