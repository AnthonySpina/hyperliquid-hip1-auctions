# Hyperliquid HIP-1 Auction Revenue

Two scripts for fetching, verifying, and auditing Hyperliquid HIP-1 spot deployment auction revenue.

## Scripts

### `hip1_auctions.py` — Revenue by Year with Three-Source Price Verification

Fetches every HIP-1 auction from HypurrScan and computes USD revenue, with independent price cross-checks for HYPE-era auctions across three sources.

**How it works:**

HIP-1 auctions have two eras based on the `deployGas` field:

| Era | `deployGas` sign | Value |
|---|---|---|
| USDC-era | ≥ 0 | Already USD — no conversion needed |
| HYPE-era | < 0 | HYPE quantity — must convert to USD at auction date price |

For HYPE-era auctions, prices are fetched from three independent sources and compared:

| Source | Method | Coverage | Notes |
|---|---|---|---|
| DeFiLlama | Per auction date, noon UTC | Full history | Primary source for USD conversion |
| Gate.io | Bulk daily close (HYPE_USDT) | Full history | Primary cross-check |
| OKX | Paginated daily close (HYPE-USDT) | Nov 2025+ | Supplemental; thin liquidity pre-Jan 2026 makes early data unreliable |

Per-auction verification flags:
- `✓` — DL vs Gate.io within 5% (normal intraday timing difference)
- `~ Gate X.X%` — 5–8% gap, within warn threshold
- `⚠ DL-Gate X.X%` — gap exceeds 8%, flagged for review

**Why gaps exist (expected):** DeFiLlama records prices at noon UTC; Gate.io and OKX record daily closes at midnight UTC. HYPE is volatile — 2–5% intraday swings are normal. Gaps are non-systematic (neither source is consistently higher), so they cancel in annual totals.

**Output:**
- Per-year tables: HYPE-era auctions with all three prices + verification status; USDC-era auctions with USDC amounts
- Annual totals in DL, Gate.io, and OKX prices with delta
- All-time grand total with overall DL vs Gate.io divergence %
- Verification summary: source coverage, gap stats (avg/median/max), list of any >8% outliers, overall verdict (CONFIRMED / SUBSTANTIALLY CONFIRMED / REVIEW NEEDED)

**Verified constants:**
- `deployGas` scale confirmed: JEFF 2024-05-24 raw=`1725.35` → $1,725 ✓; PERP 2025-05-26 raw=`-978.38` → 978 HYPE ✓
- OKX Nov 2025 – Jan 2026 gaps are structural (thin post-listing order book), not data errors

---

### `hip1_completeness_check.py` — HypurrScan Coverage Audit

Cross-checks HypurrScan `/pastAuctions` against Hyperliquid's own `spotMeta` API, which is the true ground truth for every token ever deployed.

**How it works:**

1. Fetches all tokens from `POST api.hyperliquid.xyz/info` `{type: spotMeta}`
2. Fetches all auctions from HypurrScan `/pastAuctions`
3. Excludes known non-auction tokens:
   - `USDC` — genesis stablecoin (index 0), no auction
   - `PURR` — fair-launch community airdrop (index 1), no auction gas paid
4. Diffs both sets in both directions:
   - Tokens in HL spotMeta absent from HypurrScan (missing auctions)
   - Tokens in HypurrScan absent from HL spotMeta (phantom records)

**Output:**
- Token counts: HL total, non-auction excluded, auctionable set, HypurrScan count, matched overlap
- Table of missing tokens with HL index, `isCanonical` flag, and `tokenId`
- Table of any HypurrScan records not in HL spotMeta
- Summary counts

**Key findings:**

HypurrScan is not exhaustive. Tokens confirmed missing fall into distinct categories:

| Category | Examples | Status |
|---|---|---|
| Bridge-deployed (genesis holder = `0x2000…` vault) | AXL, BZEC, USDUC, BRLA | Genuine HIP-1 — paid HYPE gas normally |
| Standard HIP-1 tokens HL indexed, HypurrScan missed | VULT, NBT, UMON, UMEGA, HMT, UVIRT | Genuine HIP-1 — paid HYPE gas normally |
| Native L1 HYPE token (index 150, `deployer=None`, `deployGas=0`) | HYPE | Not an auction — excluded |
| Anomalous (`tokenDetails` returns null) | CHECK | Unknown state — excluded |

Total genuine missed auction revenue: ~$246K across 10 tokens (Oct 2025 – Feb 2026).

## Data Sources

| Source | Endpoint |
|---|---|
| HypurrScan auctions | `api.hypurrscan.io/pastAuctions` |
| Hyperliquid spot meta | `api.hyperliquid.xyz/info` `{type: spotMeta}` |
| DeFiLlama HYPE price | `coins.llama.fi/prices/historical/{ts}/coingecko:hyperliquid` |
| Gate.io OHLCV | `api.gateio.ws/api/v4/spot/candlesticks` (HYPE_USDT, 1d) |
| OKX OHLCV | `okx.com/api/v5/market/history-candles` (HYPE-USDT, 1D) |

## Usage

```bash
pip install requests

python3 hip1_auctions.py            # revenue + price verification
python3 hip1_completeness_check.py  # HypurrScan coverage audit
```

`hip1_auctions.py` runtime: ~2–3 minutes (rate-limited DeFiLlama price calls, one per unique auction date).
