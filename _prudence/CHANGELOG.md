# Prudence — Edit History of Major Changes

This is the record of major changes and additions to the Prudence analysis and
dashboard. It is **append-only**: entries are added over time and never removed.
You can **read** this history, but it is **not** a way to roll the dashboard back
to an older version.

**How to read it:** the most recent change is at the top. Each entry has a date, a
short title, and a plain-language description of what changed and why.

> Finding this file by verbal instruction: *"Open the Sovereign AI folder, go into
> the `_prudence` folder, and open `CHANGELOG.md`. The newest changes are at the top."*

---

## 2026-06-11 — Agent Specification v2: Prudence becomes a team, with adversarial review

**What changed:** The agent spec (`_prudence/PRUDENCE_AGENT.md`) was revised to v2,
same day as v1, with four additions. (1) **Evidence & Retrieval Protocol (§6)** —
rules may only be cited as located verbatim quotes; every number must be re-traced
from source at writing time; no falling back to general knowledge. (2)
**Corroboration & Escalation Doctrine (§7)** — each severity now has explicit proof
requirements; findings that don't meet them are demoted or withdrawn, and review
can only confirm or demote, never escalate. (3) **The Agent Roster & Orchestration
(§8)** — Prudence now runs as a team of six real subagents: three Analysts (rules,
structure, composition) draft findings independently and in parallel, then every
finding must survive an adversarial **Review Chain** — an Advocate who constructs
the strongest innocent explanation and tries to kill the finding, an Equity Auditor
who independently runs the party-flip and allegation scans, and a Citation Verifier
who re-traces every quote and number. Surviving challenges are published alongside
the finding, not hidden. (4) **Module 2 expanded** into the Workplace Structure &
Human-Risk Screen with two lenses: the existing risk-factor lens (EEOC 2016,
Sinnamon, CRS R46262) and a new healthy-structure lens that will compare offices
against peer-reviewed research on successful workplace structures and why they
work. The healthy-structure lens is **not-assessable until that literature is
filed** under `_research/papers/workplace-structures/` — Prudence does not reason
from general knowledge. Output schema bumped to `prudence-v2` (findings now carry
a published `review` block recording the challenge and its answer).

**Why:** Nothing should reach a human reviewer that has not been independently
challenged first. Separating the analysts from the reviewers — as distinct agents
that cannot see each other's reasoning — makes the challenge genuinely
independent, and embodies the Charter's plurality-of-considerations principle in
the system's own architecture. The healthy-structure lens gives the workplace
screen its constructive counterpart: knowing what protective structures look
like, not only what dangerous ones do.

---

## 2026-06-11 — Established the Prudence Agent Specification (v1)

**What changed:** Prudence gained an operational layer beneath the Charter:
`_prudence/PRUDENCE_AGENT.md`. It defines the per-member analysis pipeline — the
run command ("run Prudence on <member>"), the four analysis modules (MRA Spending
& Rules Check; Workplace Structure & Power-Imbalance Screen; Vendor Composition
Screen; platform-level Reform Options), the mandatory self-checks (including the
party-flip test), the `prudence-v1` output schema written to each member's
`prudence.js`/`prudence.json`, the shared severity vocabulary, and the verbatim
module disclaimers. The spec is self-contained so it can later serve as the
system prompt for a headless automated pipeline.

**Why:** Until now the Prudence analysis was hand-authored and existed for one
member only. This spec turns Prudence into a repeatable per-member analysis that
applies the same rules, framing, and honesty requirements to every member alike —
including regenerating the original member through the same pipeline. The Charter
remains binding and prevails over the spec wherever the two could conflict.

---

## 2026-06-06 — Added retrieval & AI-integrity frameworks; filed the founding encyclical

**What changed:** Five reference documents that Prudence should reason within were
filed into the project so they are actually part of her source corpus (previously
they sat outside the repo in a working folder, where Prudence had no access). Four
went to `_research/papers/` — three peer-reviewed RAG papers (*One-shot vs Iterative
Retrieval* 2509.04820; *RAG Security & Privacy Threat Model* 2509.20324; *RAGShield:
Numerical Claim Manipulation in Government RAG* 2604.00387) and a general *RAG
systems* reference — and are catalogued under a new "Retrieval & AI-Integrity
Frameworks" section in `_research/papers/INDEX.md`. The founding encyclical
*Magnifica Humanitas* (Leo XIV, 15 May 2026) — which the Charter §2.3 is built on —
was filed beside the Charter in `_prudence/`.

**Why:** Prudence reasons only within the documents in her source folders
(`CLAUDE.md` / Charter §4). These RAG frameworks govern how she retrieves evidence
and protects her own numeric/financial claims from manipulation — a direct extension
of her integrity commitments — and the encyclical that grounds her Charter now lives
inside the project rather than only as an external copy.

**Triggered by:** Amanda Koski (custodian).

---

## 2026-06-05 — Added Situational Analysis screen (Findraiser / Wolf / Gomez)

**What changed:** A new screen — **③ Situational Analysis** — was added to the Prudence module in `article_one_beta.html`. It summarizes three interconnected publicly reported facts (the Wolf–Gomez affair allegation; the co-founding of Findraiser by Swalwell and Wolf while Wolf was COS; and the financial nexus between Findraiser and Gomez's campaign) and cross-checks them against five policy areas: (1) staff outside employment and conflict of interest per the Members' Congressional Handbook; (2) Member use of official office to promote a private venture per the House Ethics Manual and CAA; (3) workplace conduct and power dynamics per the CAA, OCWR, and EEOC 12-factor framework; (4) financial nexus between the personal relationship and commercial transaction; and (5) a structural note that the company's formation itself is not prohibited. The Prudence badge count was updated from 3 to 4.

**Why:** The custodian requested the analysis following public reporting in June 2026. All findings are framed as questions for human review — no legal conclusions are asserted. The analysis is non-partisan and cites primary source reporting.

**Triggered by:** Amanda Koski (custodian).

---

## 2026-06-05 — Added Reform Options screen (AI-generated recommendations)

**What changed:** Re-examined the data on both Prudence analysis screens and added a
third screen to the dashboard, **③ Reform Options**. It surfaces five non-partisan
legislative/policy reform recommendations drawn directly from the findings:
(1) structured purpose codes on SOD line items, (2) addressing the "use it or lose
it" allowance incentive behind the year-end lump-sum surge, (3) automated
duplicate-payment detection at the CAO, (4) a standardized machine-readable SOD
schema, and (5) a voluntary, confidential workplace-structure self-assessment via
OCWR. The existing About screen was renumbered to ④.

**Labeling:** Per the custodian's instruction, every reform recommendation is
clearly and repeatedly marked as an **AI-generated recommendation for a human to
decide** — a top-of-screen banner, a striped per-card badge, a "for human decision —
not adopted policy" note on each card, and a footer disclaimer. Nothing is presented
as adopted policy, endorsement, or proposed legislation, and nothing favors a party
or individual.

**Why:** The reform options operationalize the core Prudence vision — AI evaluates
risk and gives the human options — while honoring the human-in-the-loop and
non-partisanship principles of the Charter and *Magnifica Humanitas*.

**Triggered by:** Amanda Koski (custodian).

---

## 2026-06-05 — Prudence module formalized in the dashboard

**What changed:** The existing "Sovereign House AI" module in the dashboard
(`dashboards/swalwell_v2.html`) was formalized as **Prudence**. Its two analysis
screens were retained — ① MRA Spending & Rules Check and ② Workplace Structure &
Power-Imbalance Screen — and a third screen was added: **③ About Prudence & Change
History**. The new screen states Prudence's operating principles (human-in-the-loop,
non-partisanship, *Magnifica Humanitas* grounding, bounded by provided rules) and
renders this change history for human readers inside the dashboard.

**Why:** So the principles that bind Prudence and the record of major changes are
visible to dashboard viewers and findable by simple verbal instruction — "open the
Prudence tab and click About Prudence & Change History."

**Triggered by:** Amanda Koski (custodian).

---

## 2026-06-05 — Prudence established

**What changed:** Prudence was formally established as a decision-support system
for the legislative branch. Its operating constitution was written
(`_prudence/PRUDENCE_CHARTER.md`), grounding the system in human-in-the-loop
decision-making, non-partisanship, and the principles of Pope Leo XIV's encyclical
*Magnifica Humanitas* (May 15, 2026).

**Why:** To define — before any analysis is produced — how Prudence works, what she
will and will not do, which rules govern her, and how her changes are recorded.

**Triggered by:** Amanda Koski (custodian).

---

<!--
  ENTRY TEMPLATE — copy above this line, newest on top.

  ## YYYY-MM-DD — Short title

  **What changed:** Plain-language description of the major change or addition.

  **Why:** The reason for it.

  **Triggered by:** Who requested / initiated the change.
-->
