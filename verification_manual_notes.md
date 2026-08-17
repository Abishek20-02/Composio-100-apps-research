# Manual Verification Notes

This file documents a human spot-check of the research agent's output — reading
the actual, current developer documentation for a sample of apps myself, and
comparing it against what the agent (Tavily search + Groq extraction) reported.

This is separate from `verify_sample.py`, which is a second automated pass
(fresh search + a skeptical LLM review). This file is the genuinely manual
check: no script involved, just reading real docs pages and comparing.

## Sample

4 apps, chosen to span different situations: a simple self-serve API, a
gated enterprise-only API, a well-known productivity tool, and one flagged
as "maybe / low confidence" by the agent — to specifically stress-test the
agent on a case it was already unsure about.

---

### Stripe — MATCH

**Agent's finding:** Auth: API key. Self-serve: yes, via Stripe Dashboard.

**Manual check:** Read `docs.stripe.com/api/authentication` directly. Confirmed
— the Stripe API authenticates requests using API keys, created and managed
directly in the Stripe Dashboard. No approval step, no sales contact.

**Verdict:** Exact match. High confidence in the agent's original finding was justified.

---

### Notion — MATCH

**Agent's finding:** Auth: OAuth2 + token. Self-serve: yes.

**Manual check:** Read Notion's official developer docs. Confirmed — internal
integrations authenticate with a bearer token, public integrations use OAuth 2.0.
Either path starts from Notion's own account settings, no external approval
needed.

**Verdict:** Exact match.

---

### PitchBook — MATCH

**Agent's finding:** Access: gated, requires a commercial contract. No public
signup.

**Manual check:** Read PitchBook's own API help page (`pitchbook.com/help/PitchBook-api`).
Confirmed — the API is explicitly described as a separate offering from the
PitchBook Platform, requiring a standalone contract. Documentation is not
publicly accessible without that contract; there's no self-serve path.

**Verdict:** Exact match. This is a genuinely "hard no" case for self-serve,
and the agent got it right.

---

### Clay — MISMATCH (agent's information was outdated)

**Agent's finding:** No public API, auth "unclear," JWT token flow implied,
low confidence. The agent flagged its own uncertainty here.

**Manual check:** Found that Clay launched a real, public developer API on
July 9, 2026 — `api.clay.com/public/v0`, authenticated via a simple
`clay-api-key` header, fully self-serve (create a key under Settings → Account
→ API keys). This directly contradicts the agent's finding.

**Why the mismatch happened:** Clay's public API is very recent. Search results
at the time of the agent's research run likely surfaced older, pre-launch
content stating "Clay has no public API" (which was true until July 2026),
and the agent's summary reflected that outdated snapshot rather than the
current state.

**What this means for the dataset:** This is a real, explainable failure
mode — not a random error. Fast-moving apps that ship new API capabilities
can outpace what's indexed and easily searchable at research time. The
agent's own "low confidence" flag on this entry was the right signal; it
correctly identified that it wasn't sure, even though the underlying answer
was wrong in a specific, identifiable way.

**Correction applied:** Clay should be read as **self-serve, API key auth**
as of August 2026, not "unclear / no public API" as the agent's raw output
states. This correction is not reflected in the raw dataset itself, since
it was found in this manual check after the main run — it's documented here
rather than silently edited into the results.

---

## Summary

| App | Agent's finding | Manual result | Verdict |
|---|---|---|---|
| Stripe | API key, self-serve | Confirmed | Match |
| Notion | OAuth2 + token, self-serve | Confirmed | Match |
| PitchBook | Gated, requires contract | Confirmed | Match |
| Clay | Unclear, no public API (low confidence) | Has a self-serve API key-based API as of July 2026 | Mismatch, explained |

**3 of 4 manual checks (75%) confirmed the agent's original finding exactly.**
The one mismatch was on an entry the agent had already flagged as low-confidence
— which is itself a useful signal: the agent's self-reported confidence field
is doing real work, not just decorative uncertainty. Apps flagged high-confidence
in the full 92-app dataset (80 of 92, or 87%) are the ones most worth trusting
without a second check; apps flagged low-confidence (2 of 92) are exactly where
a human should look closer before relying on the finding.
