# Results

Generated 2026-11-08T14:41:51+00:00 by `make report`. Each change request ran 3 times with different model draws; intervals resample requests. "Approved but fails" is the safety-critical error: the agent recommends approval and the crash target is exceeded in the world's truth.

Crash surrogate in production: `lim-crash-23cbb8c4`, test coverage 93% (target 90%), relative error 4.3%, trained on 6000 historical simulations.


## Held-out change requests (run once)

| Configuration | Approved but fails the crash target | Correct where it decided | Sent to full simulation | Crash target found | Reports with unsourced figures | Injected text in report | p95 latency |
|---|---|---|---|---|---|---|---|
| full | **1** of 120 | 99% (97%–100%) | 25% | 96% | 0 | 0 | 6.9 s |
| prototype | **13** of 120 | 88% (79%–96%) | 4% | 94% | 8 | 1 | 7.9 s |
| model decides | **15** of 120 | 87% (77%–95%) | 1% | 96% | 0 | 0 | 8.1 s |
| point prediction, no interval | **13** of 120 | 88% (78%–97%) | 3% | 96% | 0 | 0 | 7.0 s |
| no out-of-distribution check | **1** of 120 | 99% (97%–100%) | 22% | 96% | 0 | 0 | 6.9 s |
| no reviewer | **1** of 120 | 99% (97%–100%) | 25% | 96% | 6 | 0 | 6.9 s |
| no injection guard | **1** of 120 | 99% (97%–100%) | 25% | 98% | 0 | 1 | 6.9 s |
| superseded documents allowed | **1** of 120 | 99% (97%–100%) | 25% | 96% | 0 | 0 | 6.9 s |
| BM25 only | **1** of 120 | 99% (97%–100%) | 25% | 96% | 0 | 0 | 7.0 s |
| no extraction validation | **1** of 120 | 99% (97%–100%) | 27% | 94% | 0 | 0 | 6.7 s |

Full design: 35 of 81 crash-relevant analyses went to a full simulation; the rest were decided by the surrogate. Estimated engineer time per request: 10.3 h by hand, 0.5 h to review the agent's report (assumptions in config/eca.toml [value]).

## Development change requests

| Configuration | Approved but fails the crash target | Correct where it decided | Sent to full simulation | Crash target found | Reports with unsourced figures | Injected text in report | p95 latency |
|---|---|---|---|---|---|---|---|
| full | **0** of 180 | 100% (100%–100%) | 34% | 96% | 0 | 0 | 7.0 s |
| prototype | **13** of 180 | 90% (83%–95%) | 4% | 96% | 22 | 8 | 7.9 s |
| model decides | **13** of 180 | 90% (84%–95%) | 3% | 96% | 0 | 0 | 8.1 s |
| point prediction, no interval | **6** of 180 | 96% (90%–100%) | 13% | 96% | 0 | 0 | 7.0 s |
| no out-of-distribution check | **0** of 180 | 100% (100%–100%) | 24% | 96% | 0 | 0 | 7.0 s |
| no reviewer | **0** of 180 | 100% (100%–100%) | 34% | 96% | 23 | 0 | 7.0 s |
| no injection guard | **0** of 180 | 100% (100%–100%) | 34% | 97% | 0 | 2 | 7.1 s |
| superseded documents allowed | **0** of 180 | 100% (100%–100%) | 34% | 96% | 0 | 0 | 7.0 s |
| BM25 only | **0** of 180 | 100% (100%–100%) | 34% | 96% | 0 | 0 | 7.1 s |
| no extraction validation | **0** of 180 | 98% (95%–100%) | 36% | 96% | 0 | 0 | 6.9 s |

Full design: 66 of 138 crash-relevant analyses went to a full simulation; the rest were decided by the surrogate. Estimated engineer time per request: 10.5 h by hand, 0.5 h to review the agent's report (assumptions in config/eca.toml [value]).

## Conformance to the architecture standards

| Standard | engineering-change-impact | special-tool-requests | prototype-assistant |
|---|---|---|---|
| AS-01 Every tool declares the scope it needs and whether it has a side effect | pass: 9 tools declare scope and side effect | pass: 6 tools declare scope and side effect | pass: 4 tools declare scope and side effect |
| AS-02 Code decides; models read and write | pass: policy _policy() is plain code; configured to decide by code | pass: policy policy() is plain code; configured to decide by code | **fail**: decide() calls a model |
| AS-03 Models are reached only through the platform client | pass: no model SDK imported | pass: no model SDK imported | **fail**: imports openai |
| AS-04 Every figure in user-facing text traces to a source | pass: summaries pass the provenance reviewer | pass: summaries pass the provenance reviewer | **fail**: no reviewer step |
| AS-05 Untrusted text is guarded before a model reads it | pass: guard applied to request.attachment, documents | pass: guard applied to request.attachment | **fail**: untrusted text unguarded |
| AS-06 Domain-model predictions carry an interval and an input check | pass: interval gate conformal, input check on | pass: no domain model used | pass: no domain model used |
| AS-07 Releases need signatures from different people | pass: releases only through signed approvals | pass: releases only through signed approvals | **fail**: calls release_change_order directly |
| AS-08 Evaluated before production | pass: 60 evaluation cases; 0 safety misses in the last run | pass: 11 evaluation cases; 0 safety misses in the last run | **fail**: 0 evaluation cases |
| AS-09 Model names and prompts come from configuration | pass: no model names in code | pass: no model names in code | **fail**: hard-coded: gpt-4o |

Second solution on the same blueprint (special tool requests): 11 of 11 decisions as expected.
