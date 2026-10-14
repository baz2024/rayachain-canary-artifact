<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# X1 — End-to-end transport run on LayerZero test networks (protocol)

**Status: NOT RUN.** `data/` and `results/` are intentionally empty. Nothing in
this folder is a measurement. Manuscript reference: Section 7.5, Table 13 (X1);
the claims it would test are architectural (status ARCH) in the paper.

**Answers:** Reviewer 1 comment 2 and Reviewer 2 comment 15 (and part of
R2.9, R2.13, R2.14). The run sends transactions from the authors' own test
wallets; it must be run by the authors.

## Setup
1. Deploy on at least three test networks, including one non-EVM chain
   (for example Ethereum Sepolia, Base Sepolia, Arbitrum Sepolia and Solana
   devnet).
2. Contracts: a sender that accepts a CanarySignal v1 envelope (compact and
   extended forms; `../canary_schema.py` is the reference encoding) and sends
   it as a LayerZero V2 message; a receiver/consumption contract that verifies
   the envelope signature, checks the validity window, decodes the fields and
   stores `(subject_key, class, type, value_bps, confidence_q7, window_end)`;
   an off-chain signer key held by the authors.
3. Record the LayerZero configuration per lane: DVNs (required/optional and
   threshold), executor, confirmations, `maxMessageSize`.
4. Workload: synthetic signals (no real subjects needed) at 1, 10 and 60
   signals per minute per lane for at least 24 h per rate; 50/50 compact and
   extended envelopes; subjects drawn from the CAIP-10 examples and random
   EVM/Solana accounts.
5. Write a pre-registration note (rates, durations, lanes, analysis) into
   `data/` and commit it **before** the run.

## Measurements (per lane, per rate)
- Propagation latency: source-transaction block timestamp to destination
  receive-transaction block timestamp (and to the consumer's decode event);
  median, 95th and 99th percentiles.
- Delivery success rate: delivered / sent within the validity window; every
  failure listed with its cause (verification timeout, executor failure,
  out-of-window rejection, decode error).
- Payload size on the wire; native fee quoted and paid per message;
  destination gas for verification + decode + storage.
- Consumer decode success; tampered-envelope injection (expect 100% rejection).
- Optional: one lane over a second transport (e.g. CCIP) to test the
  substitutability claim of Section 4.6.

## Expected outputs (once run)
- `data/messages.csv`: one row per message (lane, GUID, source and destination
  tx hashes, timestamps, envelope form, bytes, fees, gas, outcome).
- `data/deployment.json`: contract addresses and lane configurations.
- `results/summary.csv`: latency/success/fee table per lane and rate.
- Add SHA-256 checksums of every new file to `../SHA256SUMS`.
