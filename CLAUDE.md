# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Scripts

```bash
pip install requests

python3 hip1_auctions.py            # HIP-1 revenue + three-source price verification (~2–3 min)
python3 hip1_completeness_check.py  # HypurrScan coverage audit vs HL spotMeta (~5 sec)
python3 hl_buyback_model.py         # Full HYPE buyback income statement + AQA scenarios (~3–5 min)
```

No build step, no test suite. Scripts are self-contained and print directly to stdout.

## Architecture

Three independent scripts; no shared modules. Each fetches live data on every run — there is no local cache or database.

### `hip1_auctions.py`
Computes HIP-1 auction revenue by year with three-source price cross-check.

- **Step 1**: Fetch all auctions from HypurrScan `/pastAuctions`. Split into USDC-era (`deployGas ≥ 0`, value is USD directly) and HYPE-era (`deployGas < 0`, value is HYPE quantity requiring conversion).
- **Step 2**: For HYPE-era auctions, fetch prices from DeFiLlama (noon UTC, per date), Gate.io (bulk daily close), and OKX (paginated daily close, Nov 2025+). The `near()` helper checks ±1 day to handle timestamp alignment differences.
- **Step 3**: For each HYPE-era auction, compare DL vs Gate.io (primary) and DL vs OKX (supplemental). Flag gaps >5% as warn, >8% as error. OKX pre-Jan 2026 is known noisy (thin order book) and excluded from primary flagging.
- **Output**: Per-year tables → grand total → verification summary with overall verdict.

### `hip1_completeness_check.py`
Audits HypurrScan completeness against HL's own `spotMeta` API (ground truth).

Fetches HL `spotMeta` (all deployed spot tokens) and HypurrScan `pastAuctions`, excludes `USDC` (genesis) and `PURR` (fair-launch, no auction), then diffs both directions. Reports tokens in HL missing from HypurrScan and any phantom records in the reverse direction.

Key finding: HypurrScan is missing ~12 tokens. Of those, 10 are genuine paid auctions (~$246K) — split between bridge-deployed tokens (genesis holder = `0x2000…` vault, but normal HYPE gas paid) and standard HIP-1 tokens HL indexed but HypurrScan omitted. `HYPE` (index 150, `deployer=None`, `deployGas=0`) is the native L1 token — not an auction. `CHECK` returns null from `tokenDetails` — excluded as anomalous.

### `hl_buyback_model.py`
Full quarterly/annual income statement for the HYPE buyback program.

**Waterfall**: `gross taker fees` → less supply-side (maker rebates + HLP + HIP-3) → less builder pass-through → **NET→AF** + HIP-1 + AQA float yield = **total buyback resource**. L1 burn is a memo line (non-cash HYPE deflation, separate from AF).

**Section 3a** (HypurrScan supplement): After fetching HypurrScan auctions, cross-checks against HL `spotMeta`, fetches `tokenDetails` for missing tokens, interpolates deployment dates from bracketing token indices (stored in `_idx_ts`), and adds genuine missed auctions to `hip1_q` before any reporting.

**AQA yield**: Uses quarterly *average* of `totalSpotUSDC` (not quarter-end). Cash basis starts Oct 3, 2026 (Q4); first quarter is prorated. Three rate scenarios (3.5%/4.5%/5.5%) × three balance scenarios (flat/mid/high) = 9-cell scenario table.

**Key validated constants**:
- `SCALE = 1_000_000` — HypurrScan `/fees` raw int → USD (NOT applied to `deployGas`)
- `DEFILLAMA_START = 2024-12-23` — first day in DL daily breakdown
- `AQA_CASH_START = 2026-10-03` — first cash buyback date
- Builder residual = `gross − net − supply_side`. Validated 2026 YTD: computed $33.95M vs DL $33.89M (Δ $60K). Zero in Q1–Q2 2025 (pre-adoption).

## API Conventions

All scripts use a `fetch()` GET helper with exponential backoff. `hl_buyback_model.py` also has `fetch_post()` for the HL info API (`POST api.hyperliquid.xyz/info`). Rate limiting: DeFiLlama price endpoint gets `time.sleep(0.22)` between calls; OKX pagination gets `time.sleep(0.2)`.

Quarter boundaries are always computed in UTC via `calendar.timegm` to avoid local timezone shifts.

## Data Sources and Known Quirks

| Source | Endpoint | Quirk |
|---|---|---|
| DeFiLlama fees | `api.llama.fi/summary/fees/hyperliquid?dataType=...` | `totalDataChartBreakdown` starts 2024-12-23 |
| DeFiLlama L1 | `api.llama.fi/summary/fees/hyperliquid-l1?dataType=dailyRevenue` | Confirmed disjoint slug — no overlap with main HL fees |
| DeFiLlama price | `coins.llama.fi/prices/historical/{ts}/coingecko:hyperliquid` | Noon UTC timestamp; ±1 day lookup needed vs exchange closes |
| HypurrScan auctions | `api.hypurrscan.io/pastAuctions` | Not exhaustive — missing ~12 tokens vs HL spotMeta |
| HypurrScan fees | `api.hypurrscan.io/fees` | Raw ints; divide by `1_000_000` for USD. `deployGas` is NOT scaled. |
| HypurrScan USDC | `api.hypurrscan.io/spotUSDC` | Use `totalSpotUSDC` quarterly average, not quarter-end snapshot |
| HL spot meta | `api.hyperliquid.xyz/info` POST `{type:spotMeta}` | Ground truth for all deployed tokens |
| HL token details | `api.hyperliquid.xyz/info` POST `{type:tokenDetails, tokenId:...}` | Returns null for some tokens (e.g. CHECK) |
| Gate.io | `api.gateio.ws/api/v4/spot/candlesticks` | Daily close at midnight UTC; handles 429 via `Retry-After` header |
| OKX | `okx.com/api/v5/market/history-candles` | Paginated backwards; free tier ~8 months; noisy Nov 2025–Jan 2026 |
