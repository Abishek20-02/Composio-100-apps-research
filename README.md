# Composio Assignment — 100-App Research Agent

Research pipeline for the AI Product Ops Intern take-home. Given 100 apps, this
researches each one's auth method, self-serve vs gated access, API surface, and
whether it could be an agent toolkit today.

## Architecture

Two-step pipeline per app:
1. **Search** — Tavily (free-tier search API) finds and fetches relevant
   developer documentation content for the app.
2. **Extract** — Groq (running Llama 3.3 70B, also free tier) reads that
   fetched content and returns structured JSON findings (auth method,
   gating, API surface, buildability, evidence URL).

A second, independent pass (fresh Tavily search + a skeptical Groq review)
verifies a random sample of results and flags disagreements.

### Why this architecture, and what changed along the way

Two earlier versions of this pipeline used Google's Gemini API — first with
its built-in Google Search grounding tool, then (after that required a
funded/prepay tier) with Gemini for plain-text extraction only, paired with
Tavily for search. Both hit real billing issues: Gemini's grounding tool
needs a paid tier, and separately, the specific Gemini project's "prepay"
balance stayed at zero even after linking Google Cloud free trial credits —
apparently two different billing systems that don't automatically share
credit. Rather than keep debugging Google's billing plumbing against a real
time limit, the extraction step was moved to Groq, a different provider with
a genuinely free, no-card tier. The overall two-step "search then structure"
design didn't change — only which LLM does the structuring.

This debugging process is disclosed here deliberately, not hidden: it's a
real example of hitting a blocker mid-build and adapting the plan, which
matters as much as the final pipeline itself.

## What's in here

- `data/apps.json` — the 100 apps, structured as input data
- `research_agent.py` — Pass 1: researches every app, saves raw structured results
- `verify_sample.py` — Pass 2: independently re-checks a random sample of 20 results
- `apply_corrections.py` — merges verified corrections into a final dataset
- `output/` — where all results land (created automatically)

## How to run it

1. Install dependencies:
   ```
   pip install tavily-python groq
   ```

2. Get two free API keys (no card required for either):
   - **Tavily**: tavily.com → sign up → Settings → copy your key
   - **Groq**: console.groq.com → sign up → API Keys → create key

3. Set both as environment variables:
   ```
   set TAVILY_API_KEY=your-tavily-key
   set GROQ_API_KEY=your-groq-key
   ```
   (On Mac/Linux use `export` instead of `set`.)

4. Run the pipeline in order:
   ```
   python research_agent.py       # researches all 100 apps (~5-10 min)
   python verify_sample.py        # verifies a random sample of 20
   python apply_corrections.py    # produces the final, corrected dataset
   ```

5. Final results: `output/research_final.json`

## Where a human was needed

- Designing the two-step search/extract architecture and the verification prompt
- Manually spot-checking a handful of the verification pass's own findings
  against real docs pages (documented in `verification_manual_notes.md`)
- Interpreting the pattern-level findings — the agent returns per-app data,
  not cross-app insight; clustering and pattern-finding was done by hand
  from the final JSON
- Judging ambiguous cases where both passes disagreed with each other
- Debugging and redesigning the pipeline itself twice when different API
  providers' billing systems blocked progress — a real part of building
  this, documented above rather than smoothed over

## Honesty notes

- Some apps have thin public documentation. Where the model returned
  `"confidence": "low"`, that's preserved in the output rather than
  smoothed over.
- Tavily's search may occasionally surface a less relevant result for
  niche or ambiguously-named apps — a real failure mode, not hidden in
  the final report.
- The verification pass is itself an LLM call with fresh search — a
  stronger check than the first pass (independent search, adversarial
  framing) but not the same as a human reading primary docs for all 100.
  The manual notes file covers the subset that got that deeper check.
