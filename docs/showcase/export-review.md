---
title: CSV export access review
subtitle: Illustrative PR · Human decision pending
lang: en
theme: blueprint
template: sheet
mode: light
cols: 2
---

## A Review status {span=2}

```kv cols=5
Pull request: #42
Reviewed commit: a1b2c3d
CI: Passed
AI review: Blockers resolved
Human review: Decision pending
```

## B AI finding

The request handler checks permissions before it queues the job. The worker could still write an export after the user lost access.

## C Fix and evidence

The worker now checks access before writing the file. A regression test revokes access after the job is queued and confirms no file is written.

## D Human decision {span=2}

```callout warn Check the failure message
Does **Export unavailable** give users enough information when access is revoked? The reviewer can approve the wording, request a change, or defer.
```
