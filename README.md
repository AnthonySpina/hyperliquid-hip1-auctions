# Hyperliquid HIP-1 Auction Revenue

A self-contained script that fetches every HIP-1 spot deployment auction on Hyperliquid, converts HYPE-denominated bids to USD, and cross-verifies prices across three independent sources.

## What is HIP-1?

HIP-1 (Hyperliquid Improvement Proposal 1) is the mechanism by which projects pay to deploy a spot market on Hyperliquid. Winning bidders pay either in USDC (early era) or HYPE (current era). All proceeds accrue to the Hyperliquid Assistance Fund (AF) and are used to buy back HYPE.

## Findings (as of June 30, 2026)

| Year | Auctions | Revenue |
|------|----------|---------|
| 2024 | 174 | $9.17M |
| 2025 | 222 | $16.37M |
| 2026 YTD | 58 | $1.04M |
| **All-time** | **454** | **$26.58M** |

**Price verification (DeFiLlama vs Gate.io):** All-time total divergence **0.06%** across 168 HYPE-era auctions — confirmed across three independent price sources.

### Era breakdown
- **USDC-era** (May–Nov 2024): deployGas is a positive number = direct USD value. No conversion needed.
- **HYPE-era** (Nov 2024+): deployGas is a negative number = HYPE quantity. Converted to USD using DeFiLlama historical price at auction date, then cross-checked against Gate.io and OKX closes.

## Price Verification Methodology

| Source | Coverage | Method |
|--------|----------|--------|
| DeFiLlama | Full HYPE era | Noon UTC price via `coins.llama.fi/prices/historical` |
| Gate.io | Full HYPE era | Daily close, single bulk API call |
| OKX | Nov 2025+ | Daily close, paginated backwards |

Per-date gaps between DL and Gate.io average ~3% — expected timing noise (noon UTC vs midnight close on a volatile token). Gaps are non-systematic: DL is sometimes higher, sometimes lower. The totals, which are what matter, agree within 0.06%.

OKX data prior to January 2026 shows elevated gaps (up to 19%) due to thin post-listing order book depth. These are labeled "early liq" and excluded from the primary verification verdict.

## Usage

```bash
pip install requests
python3 hip1_auctions.py
```

Runtime: ~2–3 minutes (DeFiLlama rate-limits per-date price lookups; Gate.io and OKX are near-instant).

## Output Structure

1. **Per-year auction detail** — USDC-era rows show direct USD amount; HYPE-era rows show qty, all three prices, DL-Gate % gap, and a verification status per auction.
2. **Year totals** — DL, Gate.io, and OKX (partial) side-by-side with delta.
3. **All-time totals** — DL vs Gate.io with divergence %.
4. **Verification summary** — coverage counts, gap distribution stats, flagged dates, and overall verdict.

## Data Sources

| Data | Endpoint |
|------|----------|
| Auctions | `api.hypurrscan.io/pastAuctions` |
| DL price | `coins.llama.fi/prices/historical/{ts}/coingecko:hyperliquid` |
| Gate.io | `api.gateio.ws/api/v4/spot/candlesticks` (HYPE_USDT, 1d) |
| OKX | `okx.com/api/v5/market/history-candles` (HYPE-USDT, 1D) |

No API keys required. No rate-limit issues on Gate.io or OKX.

## Notes

- The `deployGas` field sign determines era: `≥ 0` = USDC value, `< 0` = HYPE quantity.
- Three genesis auctions (HFUN, LICK, MANLET) were free ($0) and are counted but excluded from revenue totals.
- HIP-1 revenue is separate from Hyperliquid's primary revenue streams (perp fees, spot fees). It is a smaller but structurally distinct income line for the AF.
