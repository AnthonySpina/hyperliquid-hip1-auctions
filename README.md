# Hyperliquid HIP-1 Auction Revenue

Two scripts for fetching, verifying, and auditing Hyperliquid HIP-1 spot deployment auction revenue.

---

## Results — Last Run: 2026-06-30

### `hip1_auctions.py`

**Annual Totals**

| Year | Auctions | Era | Total (DL) | Total (Gate.io) | Δ |
|---|---|---|---|---|---|
| 2024 | 174 | 174 USDC-era, 0 HYPE-era | $9.173M | $9.173M | $0.000M |
| 2025 | 227 | 112 USDC-era, 115 HYPE-era | $16.365M | $16.352M | +$0.013M |
| 2026 YTD | 53 | 0 USDC-era, 53 HYPE-era | $1.040M | $1.038M | +$0.002M |
| **All-time** | **454** | | **$26.578M** | **$26.563M** | **+$0.015M (0.06%)** |

**Price Verification Summary (HYPE-era auctions)**

| Metric | Value |
|---|---|
| HYPE-era auctions | 168 (164 unique price dates) |
| DL prices retrieved | 164/164 |
| Gate.io coverage | 164/164 dates |
| OKX coverage | 68/164 dates (Nov 2025+) |
| DL vs Gate.io avg gap | 3.26% |
| DL vs Gate.io median gap | 2.45% |
| DL vs Gate.io max gap | 12.62% (XMR1, 2025-12-17) |
| Within 5% | 127/164 (77%) |
| 5–8% range | 26 dates |
| Above 8% | 11 dates |
| **Overall verdict** | **✓ CONFIRMED — total divergence 0.06%** |

Date-level gaps >8% (all non-systematic — cancel in total):

| Date | Ticker | DL | Gate.io | Gap |
|---|---|---|---|---|
| 2025-05-29 | USDHL | $34.230 | $31.390 | 9.0% |
| 2025-06-02 | HOLY | $32.690 | $36.480 | 10.4% |
| 2025-06-20 | SSR | $37.030 | $33.341 | 11.1% |
| 2025-06-23 | THLP | $35.120 | $38.225 | 8.1% |
| 2025-10-11 | USDN | $39.954 | $36.793 | 8.6% |
| 2025-10-15 | MAWARI | $40.418 | $37.396 | 8.1% |
| 2025-12-17 | XMR1 | $27.571 | $24.481 | 12.6% |
| 2026-01-26 | AVGO | $22.268 | $24.937 | 10.7% |
| 2026-01-27 | GLD | $27.720 | $30.836 | 10.1% |
| 2026-05-22 | WBRL | $60.529 | $54.598 | 10.9% |
| 2026-05-27 | TREAD | $62.391 | $57.762 | 8.0% |
| 2026-05-27 | ONEAR | $62.391 | $57.762 | 8.0% |

---

### `hip1_completeness_check.py`

| Metric | Value |
|---|---|
| HL spotMeta tokens | 468 total |
| Non-auction excluded (USDC + PURR) | 2 |
| HL auctionable tokens | 466 |
| HypurrScan /pastAuctions | 454 |
| Matched | 454 |
| **Missing from HypurrScan** | **12** |
| Extra in HypurrScan (not in HL) | 0 |

Tokens in HL absent from HypurrScan:

| Token | HL index | Category | deployGas | Status |
|---|---|---|---|---|
| VULT | 378 | Standard HIP-1 | 545.14 HYPE | Genuine — supplemented |
| NBT | 382 | Standard HIP-1 | 538.20 HYPE | Genuine — supplemented |
| UMON | 383 | Standard HIP-1 | 749.84 HYPE | Genuine — supplemented |
| USDUC | 384 | Bridge-deployed | 699.64 HYPE | Genuine — supplemented |
| AXL | 388 | Bridge-deployed | 641.95 HYPE | Genuine — supplemented |
| BZEC | 389 | Bridge-deployed | 1280.50 HYPE | Genuine — supplemented |
| UMEGA | 403 | Standard HIP-1 | 500.00 HYPE | Genuine — supplemented |
| HMT | 405 | Standard HIP-1 | 500.00 HYPE | Genuine — supplemented |
| CHECK | 427 | Anomalous | — | tokenDetails=null; excluded |
| BRLA | 434 | Bridge-deployed | 546.88 HYPE | Genuine — supplemented |
| UVIRT | 443 | Standard HIP-1 | 500.00 HYPE | Genuine — supplemented |
| HYPE | 150 | Native L1 token | 0 (deployer=None) | Not an auction; excluded |

10 genuine paid auctions missing from HypurrScan (~$246K total, Oct 2025 – Feb 2026).

---

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

**Why gaps exist (expected):** DeFiLlama records prices at noon UTC; Gate.io and OKX record daily closes at midnight UTC. HYPE is volatile — 2–5% intraday swings are normal. Gaps are non-systematic (neither source is consistently higher), so they cancel in annual totals. 0.06% all-time divergence confirms this.

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

**Missing token categories:**

| Category | How to identify | Examples |
|---|---|---|
| Bridge-deployed | Genesis holder = `0x2000…` vault address | AXL, BZEC, USDUC, BRLA |
| Standard HIP-1 missed | Normal deployer, non-zero gas, absent from HypurrScan | VULT, NBT, UMON, UMEGA, HMT, UVIRT |
| Native L1 token | `deployer=None`, `deployGas=0` | HYPE (index 150) |
| Anomalous | `tokenDetails` returns null | CHECK |

Bridge-deployed tokens still paid genuine HYPE auction gas through the standard HIP-1 mechanism — the `0x2000…` genesis holder is just where the initial token supply was minted (a bridge vault), not an indicator of a different deployment process.

---

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
