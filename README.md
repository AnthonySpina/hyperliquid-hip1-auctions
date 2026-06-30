# Hyperliquid HYPE Buyback Revenue Model

Quarterly + annual income statement for Hyperliquid's HYPE buyback program. All figures sourced directly from public APIs (DeFiLlama, HypurrScan, Hyperliquid), independently cross-checked.

## Income Statement Waterfall

```
GROSS TRADING FEES          (DeFiLlama dailyFees — Perps + Spot Orderbook buckets)
  LESS: Supply-Side Costs   (maker rebates + HLP distributions + unit mkt + HIP-3;
                             DeFiLlama dailySupplySideRevenue — aggregate only)
  LESS: Builder Pass-Through (residual = gross − net − supply-side; validated per-quarter)
  ══════════════════════════════════════════════════════
  NET PROTOCOL REVENUE → AF  (DeFiLlama dailyRevenue; ±1.7% vs HypurrScan cumulative)

  PLUS: HIP-1 Auctions       (HypurrScan /pastAuctions + HL API supplement; 100% AF-bound)
  PLUS: AQA Float Yield (90%) (spotUSDC quarterly avg × rate × 90%; cash basis Oct 3 2026+)
  ══════════════════════════════════════════════════════
  TOTAL HYPE BUYBACK RESOURCE

  MEMO: HyperEVM L1 Burn     (EIP-1559 HYPE burn; separate deflation, not AF cash)
```

## Scripts

| Script | Purpose |
|---|---|
| `hl_buyback_model.py` | Main model — quarterly/annual waterfall + AQA scenarios |
| `hip1_auctions.py` | HIP-1 price verification — DL vs Gate.io vs OKX cross-check |
| `hip1_completeness_check.py` | HypurrScan completeness audit — HL spotMeta vs pastAuctions |

## How to Run

```bash
pip install requests
python3 hl_buyback_model.py
```

Runtime: ~2–3 minutes (rate-limited API calls for HYPE historical prices).

## Key Findings

### Revenue Scale
- **2025 NET→AF**: $817.8M (DeFiLlama dailyRevenue; ±1.7% vs HypurrScan)
- **2026 YTD NET→AF**: ~$310.8M (through late June)
- **2025 HIP-1**: $16.4M | **2026 YTD HIP-1**: growing as HYPE-era auctions scale

### Structural Findings
- **Builder codes** are the residual between gross, net, and supply-side — *not* maker rebates. Validated: 2026 YTD computed $33.95M vs DeFiLlama's own builder distribution line $33.89M (Δ < $100K). Zero in Q1–Q2 2025 (pre-adoption).
- **Maker rebates** are inside DeFiLlama's supply-side aggregate. Cannot be sub-queried via public API.
- **AQA yield base**: use quarterly average of `totalSpotUSDC`, not quarter-end. Q2 2026 avg = $1.743B vs $2.575B quarter-end — balance doubled within Q2, so a point-in-time snapshot would overstate by ~48%.
- **AQA cash timing**: yield accrues Aug 26, 2026; first cash buyback Oct 3, 2026 (Q4, not Q3).

### HypurrScan Completeness Gap
`/pastAuctions` is not exhaustive. Cross-checking against HL `spotMeta` (the true ground truth for all deployed tokens) reveals tokens with confirmed auction gas payments absent from HypurrScan:

**Missing categories:**
- **Bridge-deployed tokens** (e.g. AXL, BZEC, USDUC, BRLA): genesis holder is a `0x2000…` bridge vault, but HYPE auction gas was paid normally through HIP-1
- **Standard HIP-1 tokens** HL indexed but HypurrScan omitted (e.g. VULT, NBT, UMON, UMEGA, HMT, UVIRT)

**Excluded from supplement** (confirmed non-auction):
- `USDC` — genesis stablecoin, no auction
- `PURR` — fair-launch airdrop, no auction gas
- `HYPE` (index 150) — native L1 token (`deployer=None`, `deployGas=0`)
- `CHECK` — `tokenDetails` returns null; anomalous state

The model supplements HypurrScan at runtime by pulling `deployGas` from HL `tokenDetails` and estimating deployment dates via linear interpolation between bracketing token indices. Total supplemental revenue is ~$246K (small relative to overall HIP-1 volume but included for completeness).

### AQA Yield Scenarios (base 4.5%, 90% buyback)
| Period | Flat $1.7B | Mid $3.0B | High $4.5B |
|---|---|---|---|
| Q4 2026 (Oct 3 start, ~98% of quarter) | ~$17M | ~$30M | ~$45M |
| Full-year 2027 run-rate | ~$69M | ~$122M | ~$183M |

Rate assumption: 4.5% (1Y UST proxy; actual instrument TBD). Balance is a user-growth bet; Q1→Q2 2026 avg grew 2.46x QoQ.

## Data Sources

| Source | Endpoint | Used For |
|---|---|---|
| DeFiLlama | `api.llama.fi/summary/fees/hyperliquid?dataType=...` | Gross fees, net revenue, supply-side |
| DeFiLlama | `api.llama.fi/summary/fees/hyperliquid-l1?dataType=dailyRevenue` | HyperEVM L1 burn |
| DeFiLlama | `coins.llama.fi/prices/historical/{ts}/coingecko:hyperliquid` | HYPE historical price |
| HypurrScan | `api.hypurrscan.io/pastAuctions` | HIP-1 auction records |
| HypurrScan | `api.hypurrscan.io/fees` | Cumulative fee cross-check |
| HypurrScan | `api.hypurrscan.io/spotUSDC` | AQA USDC balance history |
| Hyperliquid | `api.hyperliquid.xyz/info` `{type:spotMeta}` + `{type:tokenDetails}` | HIP-1 completeness supplement |

## What Is Not Captured

- **HLP vault trading P&L**: volatile ±$50–200M/yr, accrues to HLP depositors not AF; UI-only, no public API
- **Maker rebate sub-line**: inside DeFiLlama supply-side aggregate, not publicly queryable separately
- **Pre-Nov 17 2024 daily breakdown**: HypurrScan starts Nov 17; earlier data is a single cumulative blob

## Independent Cross-Checks

| Check | Result |
|---|---|
| DeFiLlama net vs HypurrScan cumulative (2025) | ±1.7% ($817M vs $832M) |
| Builder residual 2026 YTD | $33.95M computed vs $33.89M DL line (Δ $60K) |
| Builder residual Q1–Q2 2025 | $0 (expected — pre-adoption) |
| DL slug disjoint (hyperliquid-l1 vs hyperliquid) | Confirmed, no double-count |
| HIP-1 absent from DL dailyRevenue | Confirmed via gross reconciliation |
| deployGas scale | JEFF 2024-05-24: raw=1725.35 → $1,725 ✓; PERP 2025-05-26: raw=−978.38 → 978 HYPE ✓ |
| HypurrScan completeness vs HL spotMeta | 10 genuine auctions missing (~$246K); supplemented at runtime |
