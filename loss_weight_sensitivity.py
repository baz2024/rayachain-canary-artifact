#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Basel Magableh and Ahod Alghuried
"""Synthetic sensitivity analysis of the validator-loss weights (alpha, beta, gamma).

WHAT THIS IS: a pure simulation on SYNTHETIC data, written for the R1 revision of
the RayaChain canary-layer paper, to show how the ranking of stylised miner
archetypes under L = a*Brier + b*Inconsistency + g*Calibration changes as the
weights move over the simplex. WHAT THIS IS NOT: evidence about real miners,
real chain events, or the predictive value of any canary-layer signal. No live
or historical data are used. The Bittensor deployment that the paper describes
was decommissioned on 2026-05-24 and is not used here.

Specification choices (made explicit because the manuscript leaves them open;
each is labelled AUTHOR TO CONFIRM in the manuscript):
  * window: N = 1000 scored queries per miner (W = 1,000 as in the focused
    companion manuscript); event base rate pi in {0.01, 0.05, 0.20};
  * latent per-query risk r ~ Beta(k*pi, k*(1-pi)) with k = 2; y ~ Bernoulli(r);
  * paired queries: 20% of queries are re-issued with no material chain-state
    change; Inconsistency = share of pairs whose two answers differ by more
    than the 1/256 quantisation step;
  * Calibration = expected calibration error over 10 bins of the stated
    confidence c (equal-width, bin width 0.1, as in the focused companion
    manuscript; --binning equal-mass reproduces the long companion report's
    alternative), against realised accuracy a = 1[(p >= 0.5) == y];
  * Brier = mean (p - y)^2.
Archetypes:
  A informative, calibrated, deterministic      p = r,               c = max(p, 1-p)
  B informative, noisy (non-deterministic)      p = clip(r + e), e~N(0, 0.15) redrawn per call, c = max(p, 1-p)
  C constant base-rate                          p = pi,              c = max(pi, 1-pi)
  D over-confident                              p = sharpen(r),      c = 0.99
  E informative, under-stated confidence        p = r,               c = 0.5
  F anti-informative (adversarial)              p = 1 - r,           c = 0.9
Usage: python3 loss_weight_sensitivity.py [--seeds 20] [--out results/loss_weight_sensitivity.json]
Standard library only.
"""
import argparse
import itertools
import json
import math
import random
import statistics
import sys

ARCH = ["A", "B", "C", "D", "E", "F"]
DEFAULT = (0.6, 0.2, 0.2)
Q = 1 / 256


def clip01(x):
    return min(1.0, max(0.0, x))


def sharpen(r):
    r = min(max(r, 1e-6), 1 - 1e-6)
    z = 4 * math.log(r / (1 - r))
    return 1 / (1 + math.exp(-z))


def answer(arch, r, pi, rng):
    if arch == "A":
        p = r; c = max(p, 1 - p)
    elif arch == "B":
        p = clip01(r + rng.gauss(0, 0.15)); c = max(p, 1 - p)
    elif arch == "C":
        p = pi; c = max(pi, 1 - pi)
    elif arch == "D":
        p = sharpen(r); c = 0.99
    elif arch == "E":
        p = r; c = 0.5
    else:
        p = 1 - r; c = 0.9
    p = round(p / Q) * Q  # quantise as in the companion determinism contract
    return p, c


BINNING = "equal-width"


def ece(conf, acc, bins=10):
    if BINNING == "equal-width":
        n = len(conf)
        tot = 0.0
        for b in range(bins):
            lo, hi = b / bins, (b + 1) / bins
            idx = [i for i in range(n) if (lo <= conf[i] < hi) or (b == bins - 1 and conf[i] == 1.0)]
            if idx:
                tot += len(idx) / n * abs(sum(conf[i] for i in idx) / len(idx) - sum(acc[i] for i in idx) / len(idx))
        return tot
    order = sorted(range(len(conf)), key=lambda i: conf[i])
    n = len(order)
    tot = 0.0
    for b in range(bins):
        idx = order[b * n // bins:(b + 1) * n // bins]
        if not idx:
            continue
        mc = sum(conf[i] for i in idx) / len(idx)
        ma = sum(acc[i] for i in idx) / len(idx)
        tot += len(idx) / n * abs(mc - ma)
    return tot


def components(pi, n, pair_frac, seed):
    rng = random.Random(seed)
    k = 2.0
    rs = [rng.betavariate(k * pi, k * (1 - pi)) for _ in range(n)]
    ys = [1 if rng.random() < r else 0 for r in rs]
    pairs = [i for i in range(n) if rng.random() < pair_frac]
    out = {}
    for a in ARCH:
        arng = random.Random(seed * 1000 + ord(a))
        ans = [answer(a, r, pi, arng) for r in rs]
        brier = sum((p - y) ** 2 for (p, _), y in zip(ans, ys)) / n
        incons = 0.0
        if pairs:
            diff = 0
            for i in pairs:
                p2, _ = answer(a, rs[i], pi, arng)
                diff += abs(p2 - ans[i][0]) > Q / 2
            incons = diff / len(pairs)
        acc = [1 if ((p >= 0.5) == (y == 1)) else 0 for (p, _), y in zip(ans, ys)]
        cal = ece([c for _, c in ans], acc)
        out[a] = (brier, incons, cal)
    return out, sum(ys)


def ranking(comp, w):
    loss = {a: w[0] * comp[a][0] + w[1] * comp[a][1] + w[2] * comp[a][2] for a in ARCH}
    return sorted(ARCH, key=lambda a: (loss[a], a)), loss


def kendall_tau(r1, r2):
    pos2 = {a: i for i, a in enumerate(r2)}
    conc = disc = 0
    for x, y in itertools.combinations(r1, 2):
        if pos2[x] < pos2[y]:
            conc += 1
        else:
            disc += 1
    return (conc - disc) / (conc + disc)


def simplex(step=0.05):
    m = round(1 / step)
    return [(i / m, j / m, (m - i - j) / m) for i in range(m + 1) for j in range(m + 1 - i)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--pair-frac", type=float, default=0.2)
    ap.add_argument("--binning", choices=["equal-width", "equal-mass"], default="equal-width")
    ap.add_argument("--out", default="results/loss_weight_sensitivity.json")
    a = ap.parse_args()
    global BINNING
    BINNING = a.binning
    grid = simplex()
    results = {"note": "SYNTHETIC simulation; not evidence about real miners or chain events",
               "n_queries": a.n, "pair_frac": a.pair_frac, "binning": a.binning, "seeds": a.seeds, "grid_points": len(grid),
               "default_weights": DEFAULT, "regimes": {}}
    for pi in (0.01, 0.05, 0.20):
        comps, def_loss, events = [], {x: [] for x in ARCH}, []
        def_rank_counts = {}
        for s in range(a.seeds):
            c, ne = components(pi, a.n, a.pair_frac, seed=1 + s)
            comps.append(c)
            events.append(ne)
            r, l = ranking(c, DEFAULT)
            def_rank_counts[" > ".join(r)] = def_rank_counts.get(" > ".join(r), 0) + 1
            for x in ARCH:
                def_loss[x].append(l[x])
        # per-component means
        comp_mean = {x: [statistics.mean(c[x][j] for c in comps) for j in range(3)] for x in ARCH}
        # sensitivity across the weight grid (averaged over seeds)
        same_rank = top_is_A = c_beats_a = 0
        taus = []
        a_top_alpha = []
        for w in grid:
            for c in comps:
                r0, _ = ranking(c, DEFAULT)
                r, l = ranking(c, w)
                same_rank += int(r == r0)
                top_is_A += int(r[0] == "A")
                c_beats_a += int(l["C"] < l["A"])
                taus.append(kendall_tau(r0, r))
        tot = len(grid) * len(comps)
        # smallest alpha (with beta = gamma = (1-alpha)/2) at which A ranks first in >= 95% of seeds
        alpha_min = None
        for i in range(0, 21):
            al = i / 20
            w = (al, (1 - al) / 2, (1 - al) / 2)
            share = sum(ranking(c, w)[0][0] == "A" for c in comps) / len(comps)
            if share >= 0.95:
                alpha_min = al
                break
        results["regimes"][str(pi)] = {
            "base_rate": pi,
            "mean_events_per_window": statistics.mean(events),
            "component_means_brier_incons_cal": {x: [round(v, 4) for v in comp_mean[x]] for x in ARCH},
            "default_loss_mean_sd": {x: [round(statistics.mean(def_loss[x]), 4), round(statistics.stdev(def_loss[x]), 4)] for x in ARCH},
            "default_rankings": def_rank_counts,
            "share_grid_same_full_ranking_as_default": round(same_rank / tot, 3),
            "share_grid_A_ranked_first": round(top_is_A / tot, 3),
            "share_grid_C_beats_A": round(c_beats_a / tot, 3),
            "kendall_tau_vs_default_min_mean": [round(min(taus), 3), round(statistics.mean(taus), 3)],
            "min_alpha_A_first_95pct_with_beta_eq_gamma": alpha_min,
        }
    json.dump(results, open(a.out, "w"), indent=1)
    json.dump(results, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
