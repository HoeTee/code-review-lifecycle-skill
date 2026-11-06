---
title: How Code Review Lifecycle works
subtitle: Review a change, verify the evidence, and give a person the merge decision
lang: en
template: doc
theme: blueprint
mode: light
source: v0.1.0 workflow instructions
---

Start with local changes or an existing PR. The agent reads trusted rules, reviews a fixed version, and verifies the affected behavior.
Repairs require authorization. A person decides after required checks pass and blockers clear.

## A The complete workflow

```flow TB
(Local change or existing PR) -> Trusted project rules
Trusted project rules -> Pin scope and version
Pin scope and version -> AI review (max 3 total)
AI review (max 3 total) -> Authorized repair: confirmed issue + permission
Authorized repair --> AI review (max 3 total): verify + re-review
AI review (max 3 total) -> (Local report): local-only scope
AI review (max 3 total) -> Current PR and CI: PR in scope
Current PR and CI -> *Human decision: checks pass + no blockers
Human decision --> Authorized repair: request changes
Human decision -> (Defer): defer
Human decision -> Merge gates: approve
Merge gates -> (Handoff or authorized merge): rules + authority
```

The first review and re-reviews share a default total of **three completed AI reviews**.
Local review, PR review, and human-requested revisions use the same count.
If round three still has blockers, stop automatic repair and present the cause and options.

## B What moves between stages

| Stage | Responsible role | Result passed forward |
|---|---|---|
| Trusted rules | Host agent | Applicable CLAUDE.md, REVIEW.md, included rules, and their trusted source |
| Scope and version | Host agent | Comparison base, reviewed commit or local snapshot, and file scope |
| AI review (max 3 total) | Independent reviewer when available, plus verification tools | Confirmed P0/P1/P2 findings, check results, evidence, and limits |
| Authorized repair | Author or authorized agent | The smallest complete fix, a new version, and repeated checks |
| Current PR and CI | Agent and platform | Current PR/head, required checks, thread state, and matching evidence |
| Human decision | Human reviewer | Approve, request changes, or defer for the exact reviewed version |
| Merge gates | Eligible, authorized operator | Platform requirements and merge authority, then handoff or verified merge state |

Missing root rules receive complete drafts for confirmation before writing.
Independent checks supported by known rules continue while drafts await confirmation.
Relevant untracked files belong to a local candidate; extra local changes stay separate from a pinned PR head.

## C The AI review loop

Use a review context separate from the author when the host supports it.
Read the full diff and follow affected callers, shared state, and failure paths.
Record unresolved P0/P1/P2 counts, triggers, impact, evidence, and processing status.

Fix confirmed defects only within existing authorization.
Repeat affected checks and review the revised code.
Creating a PR, switching methods, or restoring a session does not reset the review count.

Two failed fixes that share a premise and fail the same check trigger a direct test of that premise.
Required checks and missing evidence remain visible.
A further review beyond the limit needs a concrete plan and explicit authorization.

## D The human decision

Prepare the final human review package when required checks pass and no blockers remain.
Include key code, the full diff, findings, actual evidence, risks, and the precise decision needed.

- **Approve:** record the decision for this PR and commit, then check merge conditions.
- **Request changes:** return to authorized repair and review within the remaining budget.
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

[Skill entry](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/SKILL.md) · [Trusted rules and scope](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/references/review-target.md) · [Missing-rule drafts](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/references/review-rules.md) · [Review and revision](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/references/pr-workflow.md) · [Verification](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/references/verification.md) · [Human review](https://github.com/HoeTee/code-review-lifecycle-skill/blob/v0.1.0/references/human-review.md)

