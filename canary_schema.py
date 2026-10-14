#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Basel Magableh and Ahod Alghuried
"""Reference encoder/decoder for the chain-agnostic CanarySignal v1 envelope.

This is an OFFLINE reference implementation written for the R1 revision of
"RayaChain: An Omnichain Canary Layer ...". It is NOT a deployed component and
it does not send anything over LayerZero or any other transport. It exists to
(i) make the wire schema of Section 4.3 unambiguous and reproducible, (ii) check
that the canonical encoding is deterministic, and (iii) compute exact payload
sizes. All numbers it reports are properties of the schema, computed on
synthetic inputs; none is a measurement of a live system.

Subject identifiers follow CAIP-10 (account_id = chain_id ":" account_address,
chain_id per CAIP-2 = namespace ":" reference). Syntax (CAIP-2 / CAIP-10, status
Final, ChainAgnostic/CAIPs):
    namespace        [-a-z0-9]{3,8}
    reference        [-_a-zA-Z0-9]{1,32}
    account_address  [-.%a-zA-Z0-9]{1,128}

Canonicalisation profile (a specification choice of this paper, because CAIP-10
itself does not mandate canonicalisation): for the eip155 namespace the hex
address is lower-cased before hashing (so EIP-55 mixed-case and lower-case forms
of the same account map to the same subject key); every other namespace is
treated as case-sensitive and left unchanged.

Usage:  python3 canary_schema.py [--n 10000] [--seed 7] [--out results/schema_payload.json]
Standard library only.
"""
import argparse
import hashlib
import json
import random
import re
import struct
import sys

VERSION = 1
CLASSES = {"wallet": 0, "protocol": 1, "market": 2}

NAMESPACE_RE = r"[-a-z0-9]{3,8}"
REFERENCE_RE = r"[-_a-zA-Z0-9]{1,32}"
ADDRESS_RE = r"[-.%a-zA-Z0-9]{1,128}"
CAIP2 = re.compile(rf"^({NAMESPACE_RE}):({REFERENCE_RE})$")
CAIP10 = re.compile(rf"^({NAMESPACE_RE}):({REFERENCE_RE}):({ADDRESS_RE})$")

# Fixed-width part, big-endian:
#  version u8 | class u8 | type u16 | origin_key bytes32 | subject_key bytes32 |
#  value_bps i16 | confidence_q7 u8 | window_start u64 | window_end u64 | prov_root bytes32
FIXED = struct.Struct(">BBH32s32shBQQ32s")


class SchemaError(ValueError):
    pass


def canonical_caip2(chain_id: str) -> str:
    if not CAIP2.match(chain_id):
        raise SchemaError(f"not a CAIP-2 chain id: {chain_id!r}")
    return chain_id


def canonical_caip10(account_id: str) -> str:
    m = CAIP10.match(account_id)
    if not m:
        raise SchemaError(f"not a CAIP-10 account id: {account_id!r}")
    ns, ref, addr = m.groups()
    if ns == "eip155":
        addr = addr.lower()
    return f"{ns}:{ref}:{addr}"


def key32(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()


def q7(conf: float) -> int:
    if not 0.0 <= conf <= 1.0:
        raise SchemaError("confidence must lie in [0, 1]")
    return int(round(conf * 128))


def encode(sig: dict, extended: bool = True) -> bytes:
    """Deterministic canonical encoding. `extended` appends the human-readable
    CAIP-2 and CAIP-10 strings (length-prefixed) after the fixed-width part."""
    origin = canonical_caip2(sig["origin"])
    subject = canonical_caip10(sig["subject"])
    if sig["window_end"] < sig["window_start"]:
        raise SchemaError("window_end < window_start")
    if not -32768 <= sig["value_bps"] <= 32767:
        raise SchemaError("value_bps out of int16 range")
    fixed = FIXED.pack(VERSION, CLASSES[sig["class"]], sig["type"], key32(origin), key32(subject),
                       sig["value_bps"], q7(sig["confidence"]), sig["window_start"], sig["window_end"],
                       bytes.fromhex(sig["prov_root"]))
    if not extended:
        return fixed
    o, s = origin.encode(), subject.encode()
    return fixed + bytes([len(o)]) + o + bytes([len(s)]) + s


def decode(buf: bytes) -> dict:
    (ver, cls, typ, okey, skey, val, conf, ws, we, prov) = FIXED.unpack_from(buf, 0)
    if ver != VERSION:
        raise SchemaError("unsupported version")
    out = {"class": {v: k for k, v in CLASSES.items()}[cls], "type": typ, "origin_key": okey.hex(),
           "subject_key": skey.hex(), "value_bps": val, "confidence_q7": conf,
           "window_start": ws, "window_end": we, "prov_root": prov.hex()}
    off = FIXED.size
    if len(buf) > off:
        lo = buf[off]
        origin = buf[off + 1: off + 1 + lo].decode()
        off += 1 + lo
        ls = buf[off]
        subject = buf[off + 1: off + 1 + ls].decode()
        off += 1 + ls
        if key32(origin) != okey or key32(subject) != skey:
            raise SchemaError("string/key mismatch")
        out.update(origin=origin, subject=subject)
    if off != len(buf):
        raise SchemaError("trailing bytes")
    return out


# --- verified example identifiers (copied from the CAIP-10 test cases and the
# --- ChainAgnostic Solana namespace profile; see reference audit) ------------
EXAMPLES = {
    "Ethereum mainnet (EIP-55)": "eip155:1:0xab16a96D359eC26a11e2C2b3d8f8B8942d5Bfcdb",
    "Bitcoin mainnet": "bip122:000000000019d6689c085ae165831e93:128Lkh3S7CkDTBZ8W7BbpsN3YYizJMp8p6",
    "Cosmos Hub": "cosmos:cosmoshub-3:cosmos1t2uflqwqe0fsj0shcfkrvpukewcw40yjj6hdc0",
    "Kusama (polkadot namespace)": "polkadot:b0a8d493285c2df73290dfb7e61f870f:5hmuyxw9xdgbpptgypokw4thfyoe3ryenebr381z9iaegmfy",
    "StarkNet testnet": "starknet:SN_GOERLI:0x02dd1b492765c064eac4039e3841aa5f382773b598097a40073bd8b48170ab57",
    "Hedera mainnet": "hedera:mainnet:0.0.1234567890-zbhlt",
    "Solana mainnet": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp:7S3P4HxJpyyigGzodYwHtCxZyUQe9JiBMHyRWXArAaKv",
}

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def rand_subject(rng: random.Random):
    kind = rng.choice(["evm", "solana", "cosmos", "polkadot"])
    if kind == "evm":
        chain = rng.choice(["1", "10", "56", "137", "8453", "42161"])
        addr = "0x" + "".join(rng.choice("0123456789abcdef") for _ in range(40))
        if rng.random() < 0.5:  # random mixed case, emulating checksum-style casing
            addr = "0x" + "".join(c.upper() if rng.random() < 0.5 else c for c in addr[2:])
        return f"eip155:{chain}", f"eip155:{chain}:{addr}"
    if kind == "solana":
        return ("solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
                "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp:" + "".join(rng.choice(B58) for _ in range(44)))
    if kind == "cosmos":
        return "cosmos:cosmoshub-3", "cosmos:cosmoshub-3:cosmos1" + "".join(rng.choice("qpzry9x8gf2tvdw0s3jn54khce6mua7l") for _ in range(38))
    return ("polkadot:b0a8d493285c2df73290dfb7e61f870f",
            "polkadot:b0a8d493285c2df73290dfb7e61f870f:" + "".join(rng.choice(B58) for _ in range(47)))


def rand_signal(rng: random.Random) -> dict:
    origin, subject = rand_subject(rng)
    ws = rng.randrange(1_600_000_000, 1_800_000_000)
    return {"class": rng.choice(list(CLASSES)), "type": rng.randrange(0, 65536), "origin": origin,
            "subject": subject, "value_bps": rng.randrange(-32768, 32768),
            "confidence": rng.randrange(0, 129) / 128, "window_start": ws,
            "window_end": ws + rng.randrange(0, 7 * 86400), "prov_root": "%064x" % rng.getrandbits(256)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="results/schema_payload.json")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    # 1. payload sizes for the verified example identifiers
    sizes = {}
    for name, acct in EXAMPLES.items():
        ns, ref, _ = CAIP10.match(acct).groups()
        sig = {"class": "wallet", "type": 1, "origin": f"{ns}:{ref}", "subject": acct, "value_bps": -1200,
               "confidence": 0.75, "window_start": 1_700_000_000, "window_end": 1_700_086_400,
               "prov_root": "00" * 32}
        sizes[name] = {"caip10_chars": len(acct), "compact_bytes": len(encode(sig, extended=False)),
                       "extended_bytes": len(encode(sig, extended=True))}

    # 2. round-trip + determinism property test on synthetic signals
    ok_roundtrip = 0
    ok_determinism = 0
    for _ in range(a.n):
        s = rand_signal(rng)
        b1 = encode(s)
        d = decode(b1)
        s2 = dict(s, subject=d["subject"], origin=d["origin"], confidence=d["confidence_q7"] / 128)
        if encode(s2) == b1:
            ok_roundtrip += 1
        # an independent "relayer" that receives the same signal via a JSON
        # round trip with a different key order must produce identical bytes
        relayed = json.loads(json.dumps(dict(reversed(list(s.items())))))
        if encode(relayed) == b1:
            ok_determinism += 1

    # 3. EIP-55 casing: mixed-case and lower-case forms must share a subject key
    evm_pairs, evm_same = 0, 0
    for _ in range(1000):
        addr = "".join(rng.choice("0123456789abcdef") for _ in range(40))
        mixed = "".join(c.upper() if rng.random() < 0.5 else c for c in addr)
        k1 = key32(canonical_caip10(f"eip155:1:0x{addr}"))
        k2 = key32(canonical_caip10(f"eip155:1:0x{mixed}"))
        evm_pairs += 1
        evm_same += int(k1 == k2)

    # 4. invalid identifiers must be rejected
    invalid = ["eip155:1", "EIP155:1:0xabc", "solana::abc", "ab:1:0xabc", "eip155:1:0x/../x",
               "x" * 9 + ":1:abc", "eip155:" + "1" * 33 + ":0xabc", "eip155:1:" + "a" * 129]
    rejected = 0
    for bad in invalid:
        try:
            canonical_caip10(bad)
        except SchemaError:
            rejected += 1

    legacy_bytes20 = 4 + 20 + 2 + 2 + 1 + 8 + 8 + 32  # chainId(u32 assumed)+bytes20+type(u16 assumed)+...
    res = {
        "schema": "CanarySignal v1 (offline reference encoder; synthetic inputs)",
        "fixed_part_bytes": FIXED.size,
        "max_extended_bytes": FIXED.size + 1 + 41 + 1 + (8 + 1 + 32 + 1 + 128),
        "legacy_bytes20_schema_bytes_assumed_widths": legacy_bytes20,
        "examples": sizes,
        "property_test": {"n": a.n, "seed": a.seed, "roundtrip_ok": ok_roundtrip, "determinism_ok": ok_determinism},
        "eip55_case_canonicalisation": {"pairs": evm_pairs, "same_subject_key": evm_same},
        "invalid_ids_rejected": f"{rejected}/{len(invalid)}",
    }
    json.dump(res, open(a.out, "w"), indent=1)
    json.dump(res, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
