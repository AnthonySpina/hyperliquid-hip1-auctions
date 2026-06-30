#!/usr/bin/env python3
"""
hip1_completeness_check.py — Cross-check HypurrScan /pastAuctions completeness
against Hyperliquid's own /info spotMeta token list.

Logic:
  HL spotMeta lists every deployed spot token (index 0 = USDC genesis, rest = auctions).
  HypurrScan /pastAuctions should have a record for each auctioned token.
  Diff = tokens in HL that have no HypurrScan auction record (missing) + vice versa.
"""

import sys
import requests

def fetch(url, method="GET", payload=None, retries=3):
    import time
    for attempt in range(retries):
        try:
            if method == "POST":
                r = requests.post(url, json=payload, timeout=30,
                                  headers={"Content-Type": "application/json"})
            else:
                r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Failed: {url}\n  {e}") from e
            time.sleep(2 ** attempt)

SEP  = "─" * 90
SEP2 = "═" * 90

print("Fetching Hyperliquid spotMeta…", flush=True)
hl_meta  = fetch("https://api.hyperliquid.xyz/info", method="POST",
                  payload={"type": "spotMeta"})
hl_tokens = hl_meta.get("tokens", [])

print("Fetching HypurrScan pastAuctions…", flush=True)
hs_auctions = fetch("https://api.hypurrscan.io/pastAuctions")

# ── Build lookup sets ──────────────────────────────────────────────────────────
# HL tokens known to be non-auction (genesis / fair-launch / canonical special)
# USDC  = index 0, the native stablecoin — genesis, no auction
# PURR  = index 1, isCanonical=True, fair-launch airdrop to community — no auction
# HYPE  = the L1 staking token — not in spot universe at all, never auctioned via HIP-1
NON_AUCTION = {"USDC", "PURR"}

hl_auctionable = {
    t["name"]: t
    for t in hl_tokens
    if t["name"] not in NON_AUCTION
}

hs_names = {a["name"]: a for a in hs_auctions}

hl_names_set = set(hl_auctionable.keys())
hs_names_set  = set(hs_names.keys())

missing_from_hs   = sorted(hl_names_set - hs_names_set)   # in HL, absent from HypurrScan
extra_in_hs       = sorted(hs_names_set - hl_names_set)   # in HypurrScan, absent from HL

# ── Report ─────────────────────────────────────────────────────────────────────
print()
print(SEP2)
print("  HIP-1 AUCTION COMPLETENESS CHECK")
print(SEP2)
print()
print(f"  Hyperliquid spotMeta tokens:     {len(hl_tokens):>4}  total")
print(f"  Non-auction excluded (USDC+PURR):{len(NON_AUCTION):>4}")
print(f"  HL auctionable tokens:           {len(hl_auctionable):>4}")
print(f"  HypurrScan /pastAuctions:        {len(hs_auctions):>4}")
print(f"  Name overlap (matched):          {len(hl_names_set & hs_names_set):>4}")
print()
print(SEP)

if missing_from_hs:
    print(f"\n  ⚠  {len(missing_from_hs)} TOKENS IN HL BUT MISSING FROM HYPURRSCAN:\n")
    print(f"  {'Token':<12}  {'HL index':>8}  {'isCanonical':>12}  {'tokenId'}")
    print("  " + "─" * 65)
    for name in missing_from_hs:
        t = hl_auctionable[name]
        print(f"  {name:<12}  {t['index']:>8}  {str(t['isCanonical']):>12}  {t['tokenId']}")
else:
    print("\n  ✓  No HL tokens missing from HypurrScan")

print()
print(SEP)

if extra_in_hs:
    print(f"\n  ⚠  {len(extra_in_hs)} AUCTIONS IN HYPURRSCAN BUT NOT IN HL SPOT META:\n")
    print(f"  {'Token':<12}  {'Time':<25}  {'deployGas'}")
    print("  " + "─" * 65)
    import datetime as dt
    for name in extra_in_hs:
        a = hs_names[name]
        ts = dt.datetime.utcfromtimestamp(a["time"] / 1000).strftime("%Y-%m-%d %H:%M UTC")
        print(f"  {name:<12}  {ts:<25}  {a['deployGas']}")
else:
    print("\n  ✓  No HypurrScan auctions for tokens absent from HL spot meta")

print()
print(SEP)
print(f"\n  SUMMARY: {len(missing_from_hs)} missing from HypurrScan, "
      f"{len(extra_in_hs)} extra in HypurrScan vs HL ground truth")
print()
print(SEP2)
