---
title: How Code Review Lifecycle works
subtitle: AI reviews, fixes, and verifies the change. A person makes the final check.
lang: en
template: doc
theme: blueprint
mode: light
source: Current workflow instructions in this repository
---

Start with local changes or an existing PR. The agent reads trusted rules and pins the review scope and version.
The AI stage reviews, fixes confirmed defects, verifies, and re-reviews within that scope. A person checks the final result after required checks pass and blockers clear.

## A The default workflow

```flow TB
(Local change or existing PR) -> Trusted project rules
Trusted project rules -> Pin scope and version
Pin scope and version -> AI review
AI review -> AI repair: confirmed defect, rounds remain
AI review -> AI verification: no fix needed
AI repair -> AI verification
AI verification --> AI review: revised code, max 3 reviews
AI verification -> (Local result and report): local-only, review clear
AI verification -> Current PR and CI: PR in scope, review clear
Current PR and CI -> *Final human check: checks pass + no blockers
Final human check -> (Defer): defer
Final human check -> Merge gates: approve
Merge gates -> (Handoff or authorized merge): rules + authority
group AI stage: AI review, AI repair, AI verification
```

The first review and re-reviews share a default total of **three completed AI reviews**.
Local review, PR review, and human-requested revisions use the same count.
If round three still has blockers, stop automatic repair and present the cause and options.
CI defects and human-requested revisions return to the AI stage within the remaining review budget.

## B What moves between stages

| Stage | Responsible role | Result passed forward |
|---|---|---|
| Trusted rules | Host agent | Applicable CLAUDE.md, REVIEW.md, included rules, and their trusted source |
| Scope and version | Host agent | Comparison base, reviewed commit or local snapshot, and file scope |
| AI review | Independent reviewer when available | Confirmed P0/P1/P2 findings for a fixed version, evidence, and limits |
| AI repair and verification | Main agent | The smallest complete fix within scope, a new version, and repeated checks |
| Current PR and CI | Agent and platform | Current PR/head, required checks, thread state, and matching evidence |
| Final human check | Human reviewer | Check the final behavior, code, evidence, and risks; approve, request changes, or defer |
| Merge gates | Eligible, authorized operator | Platform requirements and merge authority, then handoff or verified merge state |

Missing root rules receive complete drafts for confirmation before writing.
Independent checks supported by known rules continue while drafts await confirmation.
Relevant untracked files belong to a local candidate; extra local changes stay separate from a pinned PR head.
Before repair, match the working tree to the reviewed version. Use an isolated working tree for a PR head when the current checkout differs, and preserve unrelated user changes.

## C The AI review loop

Use a review context separate from the author when the host supports it.
Read the full diff and follow affected callers, shared state, and failure paths.
Record unresolved P0/P1/P2 counts, triggers, impact, evidence, and processing status.

The default lifecycle includes local fixes for confirmed defects within scope.
The main agent fixes and verifies; the independent reviewer reads a fixed version without editing it.
Routine fixes do not wait for individual or per-round human approval.
Repeat affected checks and review the revised code before the final human check.
Creating a PR, switching methods, or restoring a session does not reset the review count.

Explicit read-only requests receive findings without edits.
Commits, pushes, PR writes, and merging retain their separate authorization requirements.
Unclear requirements or changes beyond scope need a concrete decision; they do not authorize a broader repair.

Two failed fixes that share a premise and fail the same check trigger a direct test of that premise.
Required checks and missing evidence remain visible.
A further review beyond the limit needs a concrete plan and explicit authorization.

## D The final human check

Prepare the final human review package after AI repair and re-review, when required checks pass and no blockers remain.
Include key code, the full diff, findings, actual evidence, risks, and the precise decision needed.
The person checks the final result and remaining risks. Routine technical fixes are handled in the AI stage.

- **Approve:** record the decision for this PR and commit, then check merge conditions.
- **Request changes:** return to AI repair, verification, and re-review within the remaining budget.
- **Defer:** preserve open decisions and evidence.

CI and AI review can run in parallel for an existing PR.
Final evidence must cover the version presented to the person.
Version changes invalidate affected evidence and decisions; verify and reconfirm those parts.

```callout info Approval, permission, and execution are separate
A chat decision does not replace required platform approval.
Merge needs an eligible operator, repository rules, and merge authorization.
The Skill guides the agent; this page does not execute the workflow.
```

## E Workflow sources

[Skill entry](../../SKILL.md) · [Trusted rules and scope](../../references/review-target.md) · [Missing-rule drafts](../../references/review-rules.md) · [Review and revision](../../references/pr-workflow.md) · [Verification](../../references/verification.md) · [Human review](../../references/human-review.md)

