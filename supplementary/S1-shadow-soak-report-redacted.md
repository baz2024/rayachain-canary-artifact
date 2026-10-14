<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Supplementary Material S1 (redacted)

**Redacted copy, prepared 2026-10-14 for the open artifact.** Removed: cloud
instance ID and region, secrets-store name, environment-variable and file
names, internal API endpoint paths, token-service tenant details, log and tool
paths, and the Bittensor testnet coldkey/hotkey addresses (none is needed to
verify a reported figure). Nothing else was changed; section numbers (§8, §11,
Table 9 …) refer to the companion technical report, not to the RayaChain
canary-layer paper. **The deployment described here was decommissioned on
2026-05-24 and cannot be re-run.** In the canary-layer paper this run has
status RET (Section 7.2, Table 10).

---

# Bittensor shadow-validator soak telemetry — 2026-05-04 → 2026-05-07

**Report compiled:** 2026-05-07 01:22 UTC
**Source:** Production logs of the OmniRisk shadow validator + miner running on Bittensor **testnet** (`--subtensor.network test`), netuid 60. Single EC2 host, single miner, single validator.

---

## What this report is — and what it is not

This is **operational soak telemetry** from a continuous-runtime shadow deployment of the OmniRisk Bittensor pipeline. It demonstrates that the validator process stays up, that the token service → OmniRisk → score path executes autonomously across token-TTL boundaries, and that the validator's per-round scoring loop runs deterministically against a placeholder miner.

It is **not** a measurement of the validator-loss decomposition specified in §8 of the manuscript (Brier accuracy + Inconsistency + Miscalibration), and it is **not** predictive-accuracy data in the H1/H2 sense (§3). Reasons are itemised in the [§5 — What is NOT in this report](#5--what-is-not-in-this-report) section below.

If this report is referenced in the manuscript, the appropriate framing is **"engineering soak validation of the token service → OmniRisk → score pipeline (the precondition for the §8 validator scoring rule to be measurable)"**, not "validator accuracy results." The latter framing would conflate this soak with the paper's own deferred quantitative claims and is inconsistent with the §11 limitations the manuscript already states.

---

## 1 — Run identifiers

| Field | Value |
|---|---|
| Network | Bittensor testnet (`--subtensor.network test`) |
| Netuid | 60 |
| Validator UID | 17 |
| Miner UID | 18 |
| Miner protocol | `Dummy(Synapse)` from `subnet-template/protocol.py` — returns `dummy_input × 2`. **Placeholder, not the §7 miner specification.** |
| Host | Single cloud virtual machine, `c6i.large` instance class [instance ID and region redacted] |
| Coldkey | [redacted; not needed to verify any reported figure] |
| Validator hotkey | [redacted] |
| Miner hotkey | [redacted] |
| Window covered | 2026-05-04 16:15:38 UTC → 2026-05-07 01:22:19 UTC |
| Wall-clock duration | ≈ 57 hours |

---

## 2 — Operational soak metrics

| Metric | Value | Notes |
|---|---|---|
| Successful round count (`final_score > 0`) | **5,097** | Rounds in which the validator queried the miner, called the OmniRisk prediction endpoint [path redacted], and computed a positive final score. |
| Auth failures | **0** | No instances of `auth_failure=true` or `Auth0 token request failed` in the validator log. |
| Auth0 token refreshes | **11** | Pattern `Refreshed Auth0 access token successfully`. Validates the TTL-driven refresh path (Auth0 default access-token TTL is 24h; the run crossed multiple TTL boundaries). |
| Validator service restarts (`NRestarts`) | **9** | Regressed from 0 at 2026-05-06 14:22 UTC. Investigation pending — see §6. |
| Miner service restarts (`NRestarts`) | **0** | Clean since 2026-05-04 16:15:34 UTC. |
| OS uptime at report time | 2 d 9 h | EC2 host has not rebooted; restarts are at the systemd-unit level. |
| Most recent validator service start | 2026-05-07 00:12:31 UTC | |
| First Auth0 refresh in window | 2026-05-04 09:23:36 UTC | |
| Last Auth0 refresh in window | 2026-05-07 00:12:52 UTC | 21 s after the most recent validator restart (post-restart token fetch). |
| `validator-set-weights` calls | **0** | Expected: `validator_permit=False` on testnet (no stake); the validator's weight-setting branch is gated by `subtensor.blocks_since_last_update(netuid, my_uid) >= tempo` AND `validator_permit=True`. |

### 2.1 — Observed final-score samples

The validator emits one structured INFO line per round of the form
`UID 18 OmniRisk scoring -> raw_score=R, confidence=C, final_score=F, requestId=...`.

Three samples spanning the 57-hour window:

| Timestamp (UTC) | `raw_score` | `confidence` | `final_score` | `requestId` |
|---|---:|---:|---:|---|
| 2026-05-05 00:50 | 0.788 | 0.534 | 0.421 | `None` |
| 2026-05-06 13:15:38 | 0.807 | 0.556 | 0.449 | `None` |
| 2026-05-07 01:22:06 | 0.789 | 0.535 | 0.422 | `None` |

**How to read these numbers.** They are highly consistent (`raw_score` ∈ [0.79, 0.81], `confidence` ∈ [0.53, 0.56], `final_score` ∈ [0.42, 0.45] across ≈48 hours). The consistency is the **expected, by-design** behaviour of a deterministic placeholder miner being scored against a stable input distribution by the OmniRisk API; it is **not evidence of predictive performance**. The miner under test (`miner.py`) returns `dummy_input × 2`, so OmniRisk receives a structurally identical payload every round modulo block-height drift in the input feed, and produces a stable score.

`requestId=None` is a known-open instrumentation gap on the OmniRisk response envelope; it does not affect the soak telemetry but does block any join from validator-side score events to OmniRisk-side audit records.

---

## 3 — Per-round scoring formula (as observed)

Per `subnet-template/validator.py`, the per-round score the validator records for a miner is

```
final_score = clamp_unit(raw_score_normalised) * confidence
```

where `raw_score_normalised` is the OmniRisk-returned `score` field (with the backward-compat divide-by-100 applied if `score > 1`), and `confidence` is the OmniRisk-returned `confidence` field. The result is exponentially-moving-averaged into the validator's `moving_avg_scores` with α = 0.1.

This is **not** the §8 validator-loss decomposition

\[
L_i = \alpha \cdot \mathrm{Brier}(\mathbf{s}_i, \mathbf{y}) + \beta \cdot \mathrm{Inconsistency}_i + \gamma \cdot \mathrm{Miscalibration}_i.
\]

The shadow run's `final_score` is the OmniRisk-side product of model output × model confidence per round; the §8 rule is a validator-side loss against realised ground-truth $\mathbf{y}$. They differ in three load-bearing ways: (i) §8 needs realised event labels $\mathbf{y}$, which the shadow run does not produce; (ii) §8 penalises inconsistency over paired queries with no material chain-state change, which requires real route queries (the shadow run uses the dummy protocol); (iii) §8 rewards calibration via reliability bins, which requires accumulated $(c, y)$ pairs.

---

## 4 — Auth0 token-refresh trace

Auth0 was rotated mid-deployment on 2026-05-04 (operator-initiated; covered by the deploy notes for that day). The validator picked up the rotated secret without restart. Eleven autonomous refreshes have since fired across the run; zero failures.

| # | Refresh timestamp (UTC) |
|---:|---|
| 1 | 2026-05-04 09:23:36 |
| 11 | 2026-05-07 00:12:52 |

Refreshes 2–10 are spaced inside that window at intervals consistent with the Auth0 access-token TTL boundary plus the per-process refresh-on-demand path (validator caches the token until 60 s before expiry, then refreshes synchronously on the next prediction call). Full list available in the validator log; the report cites only the boundary cases for brevity.

---

## 5 — What is NOT in this report

The manuscript §8 validator scoring rule decomposes per-miner loss into three terms; none of the three is computed by the shadow run. Mapping to the paper's own implementation-status table (Table 9, §11):

| §8 component | Status in this run | Why |
|---|---|---|
| Brier accuracy term ($\alpha$) | Not computed | Realised-event indicator $E_{q,t+\Delta}$ (the E1–E4 disjunction of §5.3) is a design proposal — Table 9 row "Validator scoring rule". No ground-truth $y_n$ is generated by this loop. |
| Inconsistency term ($\beta$) | Not computed | The placeholder `Dummy` protocol carries no route, so paired-query consistency at $t$, $t+\delta$ on routes is undefined. |
| Miscalibration term ($\gamma$) | Not computed | Reliability bins of $c_i$ vs realised accuracy require an accuracy stream, which (i) is absent. |
| Yuma reward share $M_j$ (Eq. 4) | Not applicable | `validator_permit = False` on testnet (no stake); the validator's `set_weights` branch never fires. |
| Population-level Yuma consensus weight $\overline{W}_j$ | Degenerate | Single-miner metagraph (UID 18 only); Eq. (4) trivialises at $|M|=1$. |

**This is consistent with the manuscript's own §11 limitations.** The manuscript already states: *"Most quantitative claims are deferred. The score-commitment contracts, the Bittensor subnet, and the evaluation framework (§6) are design proposals; this paper does not yet report AUC numbers, reward-retention curves, or measured comparisons against the baselines of §6.10."* This soak report does not contradict that — it covers a strictly upstream operational layer.

---

## 6 — Open issues that constrain the report's scope

1. **Validator service `NRestarts` = 9.** The validator service was clean (NRestarts=0) at 2026-05-06 14:22 UTC and is at NRestarts=9 with a most-recent boot at 2026-05-07 00:12:31 UTC. Nine restarts in ~10 hours, all converging at a midnight-UTC window, suggests either a scheduled trigger (logrotate? cron?) or a recurring exception in the post-Auth0-rotation token path. The miner remained NRestarts=0 throughout, so the regression is validator-side. Root-cause analysis is the next operational follow-up; until done, any quantitative claim that depends on per-round-rate continuity should treat the late window with care.

2. **`requestId = None`** on every observed final-score line. The OmniRisk response envelope is not yet returning a request identifier the validator can log, so per-round score events cannot be cross-referenced to OmniRisk-side audit records. Non-blocking for soak telemetry; blocking for any §8 Brier evaluation that needs to join validator observations to ground truth.

3. **Single-miner metagraph.** UID 18 (the OmniRisk miner) is the only miner; UID 17 is the validator. Yuma consensus arithmetic of paper Eq. (4) is degenerate at population size 1, and the §8 Inconsistency / Brier terms cannot be computed against a population of 1.

4. **Mainnet not deployed.** Every claim above is testnet-only. The manuscript's Table 9 is explicit that the cross-chain risk subnet is a design proposal; treat this report consistent with that scope.

---

## 7 — Reproducibility

- Validator entrypoint: `subnet-template/validator.py`
- Validator code patches in this build:
  - A config-logging helper redacts the client secret and API key before logging.
  - `_serve_axon_with_retry()` (miner side) loops up to 90 s waiting for the metagraph to confirm a non-`0.0.0.0` axon IP before declaring readiness.
- Configuration (API endpoint, API key, token-service tenant and client credentials) was loaded from a cloud secrets store into a local environment file at first boot. [Secret-store name, file path and variable names redacted.]
- Logs on the host: validator log (13 MB at report time) and miner log (908 KB at report time) [paths redacted]. The host and its logs were destroyed when the deployment was decommissioned on 2026-05-24.
- The figures were compiled with read-only log pattern-matching commands [tool configuration redacted].

---

## 8 — Suggested manuscript citation

If you reference this report in the manuscript, the cleanest place is a footnote in §11.1 (Implementation status, "Cross-chain risk subnet (Bittensor): Design proposal"), of the form:

> *An engineering shadow deployment of the validator + miner pipeline against Bittensor testnet (netuid 60) has been running continuously since 2026-05-04 and is reported in `bittensor-shadow-soak-2026-05-07.md`. The shadow run validates the token service → OmniRisk → per-round-score path at the operational layer (5,097 successful rounds, 0 auth failures, 11 autonomous Auth0 refreshes over a ≈57 h window) but does not produce the §8 validator-loss components, which require the realised-event channel and a non-trivial miner population. The §8 measurement is deferred to follow-up work consistent with the §13 (Roadmap) sequencing.*

This framing is consistent with the paper's existing §11 honesty about which components are deployed and which are design proposals, and avoids any over-claim that could undermine the verification-architecture thesis on review.
