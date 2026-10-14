<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# rayachain-canary-artifact

Code and data for **"RayaChain: An Omnichain Canary Layer for Cross-Chain Risk
and Credit Signal Propagation in Decentralized Agentic Finance"** (B. Magableh,
A. Alghuried; Computer Systems Science and Engineering, under review, first
revision v0.8-r1).

**What this artifact is.** Everything the paper *measures* is offline or
synthetic: an offline reference encoder for the signal envelope and a synthetic
sensitivity analysis of the validator-loss weights. Neither uses live or
historical chain data, and neither is evidence of predictive or economic
performance. The two experiments that would test the paper's open claims (X1,
X2) are included as protocols only; they have **not** been run and their
folders are empty. The OmniRisk signal-generation engine referred to in the
paper is proprietary and is **not** part of this artifact.

## Contents and what each file reproduces

| Path | Reproduces (manuscript v0.8-r1) | Licence |
|---|---|---|
| `canary_schema.py` | Section 7.3, Table 11 (envelope sizes, round-trip/determinism test, EIP-55 canonicalisation, invalid-ID rejection); fixed-part size of Table 5 | Apache-2.0 |
| `loss_weight_sensitivity.py` | Section 7.4, Table 12 (both binnings); the "Sim." entries of Table 6 | Apache-2.0 |
| `results/schema_payload.json` | Output of `canary_schema.py` | CC BY 4.0 |
| `results/loss_weight_sensitivity.json` | Output, equal-width bins (Table 12 rows 1–3) | CC BY 4.0 |
| `results/loss_weight_sensitivity_equal_mass.json` | Output, equal-mass bins (Table 12 rows 4–6) | CC BY 4.0 |
| `supplementary/S1-shadow-soak-report-redacted.md` | Supplementary Material S1: source of Section 7.2 and Table 10 (historical run of a deployment retired on 2026-05-24; cannot be re-run). Redacted, see its header | CC BY 4.0 |
| `supplementary/prediction-router-metrics-2026-05-07.csv` | Not used in any table of this paper; scheduled-evaluation metrics of the proprietary engine as reported in the companion report, included for transparency (aggregate metrics only, no identifiers) | CC BY 4.0 |
| `x1-layerzero-e2e/` | Protocol for experiment X1 (Section 7.5, Table 13). **Not run**; `data/`, `results/` empty | CC BY 4.0 |
| `x2-exploit-replay/` | Protocol for experiment X2 (Section 7.5, Table 13). **Not run**; `data/`, `results/` empty | CC BY 4.0 |

**Inputs.** None: both scripts generate their synthetic inputs from fixed
seeds (`canary_schema.py`: `--seed 7`, `--n 10000`, plus an internal list of
example identifiers copied from the CAIP-10 specification and the Chain
Agnostic Solana namespace profile; `loss_weight_sensitivity.py`: seeds 1–20,
`--n 1000`, `--pair-frac 0.2`, base rates 0.01/0.05/0.20, 0.05 weight grid).

## Requirements

CPython 3 standard library only (tested with **Python 3.14.5**).
`requirements.txt` is intentionally empty of packages.

## Commands

Run from the artifact root:

```bash
python3 -m venv venv && . venv/bin/activate        # optional; nothing to install
python3 canary_schema.py                              # -> results/schema_payload.json
python3 loss_weight_sensitivity.py                    # -> results/loss_weight_sensitivity.json (equal-width bins)
python3 loss_weight_sensitivity.py --binning equal-mass \
        --out results/loss_weight_sensitivity_equal_mass.json
shasum -a 256 -c SHA256SUMS                           # or: sha256sum -c SHA256SUMS
```

Each script also prints its JSON to standard output. Run time is under one
second each.

## Expected outputs

- `schema_payload.json`: `fixed_part_bytes` 119, `max_extended_bytes` 332,
  extended sizes 170–252 bytes for the seven examples,
  `roundtrip_ok` = `determinism_ok` = 10000, `same_subject_key` 1000/1000,
  `invalid_ids_rejected` "8/8".
- `loss_weight_sensitivity.json` (equal-width): share of grid points where the
  calibrated archetype A ranks first 0.304 / 0.692 / 0.874 for base rates
  0.01 / 0.05 / 0.20.
- `loss_weight_sensitivity_equal_mass.json`: the same share 0.95 / 1.0 / 0.99.

## SHA-256 checksums (`SHA256SUMS`)

```
429a2866fa4919fee504261b09785cff80513c166c59d6f2a14d4c2be876d20c  results/loss_weight_sensitivity_equal_mass.json
b5f8d2f951b77414e5b0713f19c30df0eac49900ea6af5132f5b9dbc4fe485c2  results/loss_weight_sensitivity.json
810bcf696c13e537969befd00cfeb6bb15e1735d61b71dcf6f8c567e69b43fd1  results/schema_payload.json
44ff09d4981129c39e26ef31109ea742ecacbf4884ef3b1ff8eb3248fca1aeb9  supplementary/prediction-router-metrics-2026-05-07.csv
56683b58c21a28e6959a9728ca9ff05af0e022124ba833a5abe542862131484b  supplementary/S1-shadow-soak-report-redacted.md
```

Reproducibility check (2026-10-14): in a fresh virtual environment outside the
source repository, the three commands above regenerated all three result files
byte-for-byte identical to the committed versions.

## Licences

- Code (`*.py`): Apache License 2.0, see `LICENSE`; SPDX headers in each file.
- Data, results and documentation (`results/`, `supplementary/`, `*.md`,
  protocols): Creative Commons Attribution 4.0 International, see
  `LICENSE-data`.

## Citation

See `CITATION.cff` (and `.zenodo.json` for archiving). The repository URL and
DOI will be added after the authors create the public repository and the first
Zenodo release.
