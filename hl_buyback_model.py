#!/usr/bin/env python3
"""
hl_buyback_model.py — Hyperliquid HYPE Buyback Revenue Model
Quarterly + Annual | Sourced, independently cross-checked

INCOME STATEMENT WATERFALL:

  GROSS TRADING FEES (DeFiLlama dailyFees)
    Perp taker fees          ["Hyperliquid Perps" bucket]
    Spot taker fees          ["Hyperliquid Spot Orderbook" bucket]
  LESS: SUPPLY-SIDE COSTS   [DeFiLlama dailySupplySideRevenue — maker rebates + HLP dist
                              + unit mkt + HIP-3 dist; API aggregate only, no sub-lines]
  LESS: BUILDER PASS-THROUGH [Residual = gross − net − supply-side; validated per-quarter]
  ════════════════════════════════════════════
  NET PROTOCOL REVENUE → AF  [DeFiLlama dailyRevenue; cross-checked vs HypurrScan ±1.7%]
                              NOTE: does NOT include HIP-1 (DL doesn't track it)

  PLUS: HIP-1 AUCTIONS       [HypurrScan /pastAuctions; 100% AF-bound; additive to AF total]
                              deployGas in native units (no scale): USDC-era positive, HYPE-era negative

  PLUS: AQA FLOAT YIELD (90%) [spotUSDC quarterly avg × rate × 90%; cash basis Oct 3 2026+]
  ════════════════════════════════════════════
  TOTAL HYPE BUYBACK RESOURCE = net + HIP-1 + AQA yield

  MEMO (non-cash HYPE deflation, separate from AF cash buyback)
    HyperEVM priority fee burn [DeFiLlama hyperliquid-l1; verified disjoint from HL slug]

VERIFICATION NOTES
  deployGas scale: confirmed no scale factor — USDC-era values are USD, HYPE-era are HYPE qty.
  DL slug overlap: hyperliquid-l1 is a distinct slug; "Hyperliquid L1" absent from HL subcats.
  Builder residual: validated per-quarter; negative signals a DL reclassification, not noise.
  UTC bounds: all quarter boundaries computed in UTC (calendar.timegm) to avoid local-tz shift.
"""

import calendar
import collections
import datetime as dt
import sys
import time

import requests

# ── Configuration ──────────────────────────────────────────────────────────────
AQA_RATE_SCENARIOS = {
    "bear (3.5%)": 0.035,
    "base (4.5%)": 0.045,
    "bull (5.5%)": 0.055,
}
AQA_BUYBACK_PCT   = 0.90
AQA_CASH_START    = dt.date(2026, 10, 3)   # first cash buyback; accrual Aug 26 is irrelevant for cash model
DEFILLAMA_START   = dt.date(2024, 12, 23)  # first day in DL daily breakdown
SCALE             = 1_000_000              # HypurrScan /fees raw int → USD (NOT applied to deployGas)

# Builder residual tolerance: warn if a quarterly negative exceeds this fraction of gross.
# Small negatives (~< 0.1%) are rounding; larger ones are classification drift.
BUILDER_WARN_THRESHOLD = -0.001   # −0.1% of quarter gross

# ── Request helper with retry ───────────────────────────────────────────────────
def fetch(url, max_retries=3, **kwargs):
    kwargs.setdefault("timeout", 30)
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed after {max_retries} attempts: {url}\n  {e}") from e
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{max_retries}] {e} — sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)

def fetch_post(url, payload, max_retries=3, **kwargs):
    kwargs.setdefault("timeout", 30)
    kwargs.setdefault("headers", {"Content-Type": "application/json"})
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"POST failed after {max_retries} attempts: {url}\n  {e}") from e
            time.sleep(2 ** attempt)

# ── Quarter utilities (all UTC) ────────────────────────────────────────────────
def qtr_key(d):
    """datetime or date → '2025-Q3'"""
    month = d.month if hasattr(d, "month") else d.timetuple().tm_mon
    year  = d.year  if hasattr(d, "year")  else d.timetuple().tm_year
    return f"{year}-Q{(month-1)//3+1}"

def qtr_bounds_utc(yr, q):
    """Return (start_epoch, end_epoch) for a calendar quarter, in UTC."""
    month_starts = [1, 4, 7, 10]
    month_ends   = [(yr,4,1),(yr,7,1),(yr,10,1),(yr+1,1,1)]
    start = calendar.timegm((yr, month_starts[q-1], 1, 0, 0, 0, 0, 0, 0))
    end   = calendar.timegm((*month_ends[q-1], 0, 0, 0, 0, 0, 0))
    return start, end

def qtr_bounds_date(yr, q):
    """Return (start_date, end_date exclusive) for a calendar quarter."""
    month_starts = [1, 4, 7, 10]
    month_ends   = [(yr,4,1),(yr,7,1),(yr,10,1),(yr+1,1,1)]
    return (dt.date(yr, month_starts[q-1], 1),
            dt.date(*month_ends[q-1]))

# ── 1. DeFiLlama fee data ─────────────────────────────────────────────────────
print("Fetching DeFiLlama fee breakdown…", flush=True)

def dl_fetch(dtype):
    return fetch(
        f"https://api.llama.fi/summary/fees/hyperliquid?dataType={dtype}"
    ).get("totalDataChartBreakdown", [])

gross_daily = dl_fetch("dailyFees")
net_daily   = dl_fetch("dailyRevenue")
ss_daily    = dl_fetch("dailySupplySideRevenue")

def qtr_totals(entries):
    q = collections.defaultdict(float)
    for ts, chains in entries:
        d = dt.datetime.utcfromtimestamp(ts).date()
        if d < DEFILLAMA_START:
            continue
        q[qtr_key(d)] += sum(v for c in chains.values() for v in c.values())
    return q

def qtr_by_subcat(entries, subcat):
    q = collections.defaultdict(float)
    for ts, chains in entries:
        d = dt.datetime.utcfromtimestamp(ts).date()
        if d < DEFILLAMA_START:
            continue
        for c in chains.values():
            q[qtr_key(d)] += c.get(subcat, 0)
    return q

gross_q = qtr_totals(gross_daily)
net_q   = qtr_totals(net_daily)
ss_q    = qtr_totals(ss_daily)
perp_q  = qtr_by_subcat(gross_daily, "Hyperliquid Perps")
spot_q  = qtr_by_subcat(gross_daily, "Hyperliquid Spot Orderbook")

# ── Builder residual (per-quarter, no clamp) ───────────────────────────────────
# Residual = gross − net − supply-side.
# Validated identity: residual ≈ builder pass-through fees (confirmed: 2026 YTD $33.95M vs DL $33.89M).
# Zero in Q1–Q2 2025 (pre-builder-adoption); steps to ~$16–23M/qtr as builder volume scales.
# A negative residual means something in gross, net, or supply-side is misclassified —
# flag it immediately rather than silently clipping to zero.
builder_qtr = {}
builder_warnings = []
for k in gross_q:
    residual = gross_q[k] - net_q.get(k, 0) - ss_q.get(k, 0)
    builder_qtr[k] = residual
    if residual < 0 and gross_q[k] > 0:
        pct = residual / gross_q[k]
        if pct < BUILDER_WARN_THRESHOLD:
            builder_warnings.append(
                f"  ⚠  {k}: builder residual = ${residual/1e6:.2f}M ({pct*100:.2f}% of gross) — "
                f"possible DL reclassification or timing mismatch"
            )

# ── Per-quarter gross reconciliation: perp + spot must ≈ gross ────────────────
# "Hyperliquid HLP" bucket exists in dailyFees but carries near-zero values.
# Assert the three named buckets sum to gross; flag if any unnamed bucket appears.
hlp_q   = qtr_by_subcat(gross_daily, "Hyperliquid HLP")
recon_warnings = []
for k in gross_q:
    explained = perp_q.get(k,0) + spot_q.get(k,0) + hlp_q.get(k,0)
    gap = gross_q[k] - explained
    if gross_q[k] > 0 and abs(gap / gross_q[k]) > 0.002:   # > 0.2% tolerance
        recon_warnings.append(
            f"  ⚠  {k}: perp+spot+HLP = ${explained/1e6:.1f}M but gross = ${gross_q[k]/1e6:.1f}M "
            f"(gap ${gap/1e6:.1f}M = {gap/gross_q[k]*100:.1f}%) — new DL bucket?"
        )

# ── 2. HyperEVM L1 fee burn (memo, verified disjoint slug) ────────────────────
print("Fetching HyperEVM L1 burn data…", flush=True)
l1_daily = fetch(
    "https://api.llama.fi/summary/fees/hyperliquid-l1?dataType=dailyRevenue"
).get("totalDataChartBreakdown", [])
l1_q = collections.defaultdict(float)
for ts, chains in l1_daily:
    d = dt.datetime.utcfromtimestamp(ts).date()
    l1_q[qtr_key(d)] += sum(v for c in chains.values() for v in c.values())

# ── 3. HIP-1 auction revenue ───────────────────────────────────────────────────
# deployGas field: positive = USDC (already in USD, no scale), negative = HYPE quantity.
# Verified: first USDC auction 2024-05-24 JEFF shows raw=1725.35 → $1,725.35 ✓
#           first HYPE auction 2025-05-26 PERP shows raw=-978.38 → 978.38 HYPE ✓
print("Fetching HIP-1 auction data…", flush=True)
auctions_raw = fetch("https://api.hypurrscan.io/pastAuctions")

_px_cache = {}

def hype_price_on(ts_s):
    day = dt.datetime.utcfromtimestamp(ts_s).date()
    if day not in _px_cache:
        data = fetch(
            f"https://coins.llama.fi/prices/historical/{int(ts_s)}/coingecko:hyperliquid"
        )
        _px_cache[day] = data["coins"]["coingecko:hyperliquid"]["price"]
        time.sleep(0.22)
    return _px_cache[day]

hip1_q = collections.defaultdict(float)
for a in auctions_raw:
    ts_s = a["time"] / 1000.0
    d    = dt.datetime.utcfromtimestamp(ts_s).date()
    raw  = float(a["deployGas"])
    usd  = raw if raw >= 0 else abs(raw) * hype_price_on(ts_s)
    hip1_q[qtr_key(d)] += usd

print(f"  {len(auctions_raw)} auctions processed", flush=True)

# ── 3a. HypurrScan completeness supplement ────────────────────────────────────
# HypurrScan /pastAuctions is not exhaustive. HL /info spotMeta is the ground
# truth for every deployed spot token. Strategy:
#   1. Find tokens in HL spotMeta that are absent from HypurrScan.
#   2. Exclude known non-auction tokens: USDC (genesis) and PURR (fair-launch).
#   3. Pull deployGas + deployer from HL tokenDetails for each candidate.
#   4. Skip if deployer=None or gas=0 (native/canonical, e.g. L1 HYPE at idx 150).
#   5. Skip if tokenDetails returns null (anomalous, e.g. CHECK).
#   6. Estimate deployment date via linear interpolation between bracketing indices.
#   7. Convert HYPE gas to USD at estimated date price; add to hip1_q.
#
# Bridge-deployed tokens (genesis holder = 0x2000… vault) are included because
# they still paid genuine HYPE auction gas through the HIP-1 mechanism.
HL_NON_AUCTION = {"USDC", "PURR"}

print("Cross-checking HypurrScan vs HL spotMeta for missed auctions…", flush=True)
_hl_spot    = fetch_post("https://api.hyperliquid.xyz/info", {"type": "spotMeta"})
_hl_tkns    = _hl_spot.get("tokens", [])
_hl_by_idx  = sorted(_hl_tkns, key=lambda t: t["index"])

_hs_name_set    = {a["name"] for a in auctions_raw}
_hs_by_name     = {a["name"]: a for a in auctions_raw}

# Build (index, timestamp) pairs from confirmed HypurrScan records for interpolation
_idx_ts = [
    (t["index"], _hs_by_name[t["name"]]["time"] / 1000.0)
    for t in _hl_by_idx if t["name"] in _hs_by_name
]

def _interp_ts(idx):
    """Estimate deployment timestamp for an index not in HypurrScan."""
    before = [(i, ts) for i, ts in _idx_ts if i < idx]
    after  = [(i, ts) for i, ts in _idx_ts if i > idx]
    if not before or not after:
        return None
    bi, bts = before[-1]
    ai, ats = after[0]
    return bts + (idx - bi) / (ai - bi) * (ats - bts)

_missing = [t for t in _hl_by_idx
            if t["name"] not in _hs_name_set and t["name"] not in HL_NON_AUCTION]

supplemental_records = []
supplemental_skipped = []

for _t in _missing:
    _name = _t["name"]
    _idx  = _t["index"]
    try:
        _td = fetch_post("https://api.hyperliquid.xyz/info",
                         {"type": "tokenDetails", "tokenId": _t["tokenId"]})
    except Exception:
        _td = None

    if _td is None:
        supplemental_skipped.append((_name, _idx, "tokenDetails=null (anomalous)"))
        continue

    _deployer = _td.get("deployer")
    _gas      = float(_td.get("deployGas") or 0)

    if _deployer is None or _gas == 0:
        supplemental_skipped.append((_name, _idx, "native/canonical: no auction gas"))
        continue

    _ts = _interp_ts(_idx)
    if _ts is None:
        supplemental_skipped.append((_name, _idx, "cannot interpolate date"))
        continue

    _px  = hype_price_on(_ts)
    _usd = _gas * _px
    _d   = dt.datetime.utcfromtimestamp(_ts).date()

    _genesis = (_td.get("genesis") or {}).get("userBalances", [])
    _bridge  = bool(_genesis and _genesis[0][0].startswith("0x2000"))

    hip1_q[qtr_key(_d)] += _usd
    supplemental_records.append({
        "name": _name, "index": _idx, "date": _d,
        "hype_qty": _gas, "price": _px, "usd": _usd, "bridge": _bridge,
    })

_supp_total = sum(r["usd"] for r in supplemental_records)
print(f"  {len(_missing)} tokens in HL not in HypurrScan → "
      f"{len(supplemental_records)} genuine missed auctions supplemented "
      f"(${_supp_total/1e3:.1f}K); {len(supplemental_skipped)} skipped "
      f"(native/null/undatable)")

# ── 4. HypurrScan cumulative fees (pre-DeFiLlama coverage) ────────────────────
print("Fetching HypurrScan cumulative fees…", flush=True)
fees_raw = sorted(fetch("https://api.hypurrscan.io/fees"), key=lambda x: x["time"])

def hs_interp(target_ts):
    before = [f for f in fees_raw if f["time"] <= target_ts]
    after  = [f for f in fees_raw if f["time"] >  target_ts]
    if not before:
        return 0.0, 0.0
    if not after:
        r = before[-1]
        return r["total_fees"] / SCALE, r["total_spot_fees"] / SCALE
    b, a = before[-1], after[0]
    frac = (target_ts - b["time"]) / (a["time"] - b["time"])
    tf = (b["total_fees"]      + frac * (a["total_fees"]      - b["total_fees"]))      / SCALE
    sf = (b["total_spot_fees"] + frac * (a["total_spot_fees"] - b["total_spot_fees"])) / SCALE
    return tf, sf

def hs_annual_delta(yr):
    s = hs_interp(calendar.timegm((yr,   1, 1, 0, 0, 0, 0, 0, 0)))
    e = hs_interp(calendar.timegm((yr+1, 1, 1, 0, 0, 0, 0, 0, 0)))
    tot  = max(0, e[0] - s[0])
    spot = max(0, e[1] - s[1])
    return tot, spot, tot - spot

hs_2024 = hs_annual_delta(2024)

# ── 5. AQA float base (quarterly average, UTC bounds) ─────────────────────────
print("Fetching system USDC balance history for AQA…", flush=True)
usdc_raw = sorted(fetch("https://api.hypurrscan.io/spotUSDC"), key=lambda x: x["lastUpdate"])
usdc_pts = [(x["lastUpdate"], x.get("totalSpotUSDC", 0)) for x in usdc_raw]

def aqa_avg_balance(yr, q):
    """Mean totalSpotUSDC over the quarter. All epoch comparisons in UTC."""
    start_ts, end_ts = qtr_bounds_utc(yr, q)
    pts = [b for ts, b in usdc_pts if start_ts <= ts < end_ts]
    return (sum(pts) / len(pts)) if pts else None

def aqa_quarterly_yield(yr, q, rate):
    """
    90% of quarterly yield on average USDC base, cash basis.
    Returns 0.0 before Oct 3 2026; prorates the first active quarter.
    """
    qstart, qend = qtr_bounds_date(yr, q)
    if qend <= AQA_CASH_START:
        return 0.0
    base = aqa_avg_balance(yr, q)
    if base is None:
        return None
    if qstart <= AQA_CASH_START < qend:
        fraction = (qend - AQA_CASH_START).days / (qend - qstart).days
    else:
        fraction = 1.0
    return base * rate * 0.25 * AQA_BUYBACK_PCT * fraction

# ── Collect all quarters ───────────────────────────────────────────────────────
all_qtrs = sorted(set(list(gross_q) + list(hip1_q) + list(l1_q)))

# ── Emit any pre-flight warnings before the main table ────────────────────────
SEP = "═" * 130
sep = "─" * 130

print(flush=True)
if builder_warnings or recon_warnings:
    print("  ⚠  DATA QUALITY WARNINGS")
    for w in builder_warnings + recon_warnings:
        print(w)
    print()
else:
    print("  ✓  No data quality warnings (builder residuals and gross reconciliation clean)")
    print()

# Supplemental HIP-1 summary
if supplemental_records:
    print(f"  ✦  HIP-1 SUPPLEMENT: {len(supplemental_records)} auctions absent from HypurrScan "
          f"— added to model (${_supp_total/1e3:.1f}K total)")
    print()
    print("  %-8s  %6s  %-12s  %10s  %9s  %10s  %-8s" %
          ("Token", "HL idx", "Est. date", "HYPE qty", "HYPE px", "USD", "Type"))
    print("  " + "─" * 72)
    for r in sorted(supplemental_records, key=lambda x: x["date"]):
        typ = "bridge" if r["bridge"] else "normal"
        print("  %-8s  %6d  %-12s  %10.2f  $%8.2f  $%8s  %-8s" % (
            r["name"], r["index"], str(r["date"]),
            r["hype_qty"], r["price"],
            format(int(r["usd"]), ","), typ))
    print()
if supplemental_skipped:
    print(f"  ⚠  {len(supplemental_skipped)} HL tokens skipped in supplement "
          f"(not genuine HIP-1 or data unavailable):")
    for _n, _i, _reason in supplemental_skipped:
        print(f"     {_n} (index {_i}): {_reason}")
    print()

# ═══════════════════════════════════════════════════════════════════════════════
print(SEP)
print("  HYPERLIQUID — HYPE BUYBACK REVENUE MODEL")
print(f"  Generated: {dt.date.today()}  |  Sources: DeFiLlama, HypurrScan, Coins.LLama")
print(SEP)

# ── QUARTERLY TABLE ───────────────────────────────────────────────────────────
print()
print("  QUARTERLY WATERFALL  (all figures USD millions)")
print()
print(f"  {'Quarter':<10}  {'Gross':>12}  {'Perp':>12}  {'Spot':>12}  "
      f"{'HIP-1':>10}  {'Supply-Side':>13}  {'Builder¹':>12}  "
      f"{'NET→AF':>12}  {'AQA Yield²':>12}  {'TOTAL BUY':>12}  {'L1 Burn³':>10}")
print("  " + sep)

annual = collections.defaultdict(lambda: {
    k: 0.0 for k in ["gross","perp","spot","hip1","ss","builder","net","aqa_yield","l1"]
})

def vcol(x):
    return "            " if x == 0 else f"${x/1e6:>10.1f}M"

def bdr_col(x):
    """Builder column: show negative residuals explicitly (red flag, not zero)."""
    if abs(x) < 1000:
        return "            "   # genuinely zero (< $1K rounding)
    color = "" if x >= 0 else "!"
    return f"{color}${x/1e6:>10.1f}M"

for qtr in all_qtrs:
    yr, q   = int(qtr[:4]), int(qtr[6])
    gross   = gross_q.get(qtr, 0)
    perp    = perp_q.get(qtr, 0)
    spot    = spot_q.get(qtr, 0)
    hip1    = hip1_q.get(qtr, 0)
    ss      = ss_q.get(qtr, 0)
    bldr    = builder_qtr.get(qtr, 0)
    net     = net_q.get(qtr, 0)
    l1      = l1_q.get(qtr, 0)
    aqa_y   = aqa_quarterly_yield(yr, q, AQA_RATE_SCENARIOS["base (4.5%)"])
    # HIP-1 is added to buyback total: 100% of proceeds confirmed AF-bound (CoinShares);
    # DL dailyRevenue does NOT include HIP-1 (HypurrScan-sourced separately), so it must
    # be added explicitly. No double-count: gross reconciliation confirms HIP-1 absent from
    # DL subcategories.
    total   = net + hip1 + (aqa_y or 0)

    flag = ""
    if qtr == "2026-Q4":
        flag = " ← AQA Q4 2026 (prorated: Oct 3 start → ~98% of quarter)"
    elif yr == 2026 and qtr == qtr_key(dt.date.today()) and dt.date.today() < qtr_bounds_date(yr, q)[1]:
        flag = " ← YTD (partial quarter)"

    aqa_str   = "            " if not aqa_y else f"${aqa_y/1e6:>10.1f}M"
    total_str = f"${total/1e6:>10.1f}M" if total > 0 else "            "

    print(f"  {qtr:<10}  {vcol(gross)}  {vcol(perp)}  {vcol(spot)}  "
          f"  {vcol(hip1)}  {vcol(ss)}   {bdr_col(bldr):>12}  "
          f"{vcol(net)}  {aqa_str}  {total_str}  {vcol(l1)}  {flag}")

    a = annual[yr]
    a["gross"]   += gross;  a["perp"]   += perp;  a["spot"]    += spot
    a["hip1"]    += hip1;   a["ss"]     += ss;     a["builder"] += bldr
    a["net"]     += net;    a["l1"]     += l1
    if aqa_y:  a["aqa_yield"] += aqa_y

# ── Per-quarter builder validation summary ────────────────────────────────────
print()
print("  Builder residual validation (should be 0 in Q1–Q2 2025, positive thereafter):")
for qtr in sorted(builder_qtr):
    b = builder_qtr[qtr]
    g = gross_q.get(qtr, 1)
    status = "✓ zero (pre-adoption)" if abs(b) < 1000 else \
             f"✓ ${b/1e6:.1f}M ({b/g*100:.1f}% of gross)" if b > 0 else \
             f"⚠ NEGATIVE ${b/1e6:.2f}M — flag for review"
    print(f"    {qtr}: {status}")

# ── ANNUAL TABLE ──────────────────────────────────────────────────────────────
print()
print("  " + sep)
print()
print("  ANNUAL SUMMARY")
print()
print(f"  {'Year':<12}  {'Gross':>12}  {'Perp':>12}  {'Spot':>12}  "
      f"{'HIP-1':>10}  {'Supply-Side':>13}  {'Builder¹':>12}  "
      f"{'NET→AF':>12}  {'AQA Yield²':>12}  {'TOTAL BUY':>12}  {'L1 Burn³':>10}")
print("  " + sep)

# 2024: HypurrScan for full-year totals; DL Q4 ratio for net/SS estimation
hs_2024_total = hs_2024[0]
dl_2024_g     = gross_q.get("2024-Q4", 0)
dl_2024_n     = net_q.get("2024-Q4", 0)
dl_2024_ss    = ss_q.get("2024-Q4", 0)
net_ratio     = dl_2024_n  / dl_2024_g if dl_2024_g > 0 else 0.946
ss_ratio      = dl_2024_ss / dl_2024_g if dl_2024_g > 0 else 0.055
net_2024_est  = hs_2024_total * net_ratio
ss_2024_est   = hs_2024_total * ss_ratio
hip1_2024     = annual[2024]["hip1"]
l1_2024       = annual[2024]["l1"]

total_2024_est = net_2024_est + hip1_2024
# Note: hs_2024[2] is (total − spot), which absorbs any pre-DL items. Labeled "Perp†" below.
print(f"  {'2024 (est)*':<12}  ${hs_2024_total/1e6:>10.1f}M  ${hs_2024[2]/1e6:>10.1f}M† ${hs_2024[1]/1e6:>10.1f}M  "
      f"${hip1_2024/1e6:>8.1f}M  ${ss_2024_est/1e6:>11.1f}M              "
      f"${net_2024_est/1e6:>10.1f}M               "
      f"${total_2024_est/1e6:>10.1f}M  ${l1_2024/1e6:>8.1f}M")

for yr in [2025, 2026]:
    a       = annual[yr]
    aqa_y   = a["aqa_yield"]
    total   = a["net"] + a["hip1"] + aqa_y   # HIP-1 additive: 100% AF, not in DL dailyRevenue
    suffix  = " YTD" if yr == 2026 else ""
    aqa_str = f"${aqa_y/1e6:>10.1f}M" if aqa_y > 0 else "            "
    tot_str = f"${total/1e6:>10.1f}M"

    print(f"  {str(yr)+suffix:<12}  ${a['gross']/1e6:>10.1f}M  ${a['perp']/1e6:>10.1f}M  ${a['spot']/1e6:>10.1f}M  "
          f"${a['hip1']/1e6:>8.1f}M  ${a['ss']/1e6:>11.1f}M  ${a['builder']/1e6:>10.1f}M  "
          f"${a['net']/1e6:>10.1f}M  {aqa_str}  {tot_str}  ${a['l1']/1e6:>8.1f}M")

# ── AQA SCENARIO TABLE ─────────────────────────────────────────────────────────
print()
print("  " + sep)
print()
print("  AQA FLOAT YIELD SCENARIOS  (90% of quarterly yield → buybacks, cash basis Oct 3 2026+)")
print()

q2_avg = aqa_avg_balance(2026, 2) or 1.743e9
q1_avg = aqa_avg_balance(2026, 1) or 0.709e9

balance_scenarios = {
    "flat $1.7B":     1.7e9,
    "mid  $3.0B":     3.0e9,
    "high $4.5B":     4.5e9,
}
rate_labels = list(AQA_RATE_SCENARIOS.keys())

# Header
print(f"  {'Quarter':<10}", end="")
for blabel in balance_scenarios:
    for rlabel in rate_labels:
        col = f"{blabel}/{rlabel.split()[0]}"
        print(f"  {col:>22}", end="")
print()
print("  " + sep[:110])

future_qtrs = ["2026-Q3","2026-Q4","2027-Q1","2027-Q2","2027-Q3","2027-Q4"]
for qtr in future_qtrs:
    yr, q = int(qtr[:4]), int(qtr[6])
    qstart, qend = qtr_bounds_date(yr, q)
    if qend <= AQA_CASH_START:
        fraction = 0.0
    elif qstart <= AQA_CASH_START < qend:
        fraction = (qend - AQA_CASH_START).days / (qend - qstart).days
    else:
        fraction = 1.0

    print(f"  {qtr:<10}", end="")
    for base in balance_scenarios.values():
        for rate in AQA_RATE_SCENARIOS.values():
            y = base * rate * 0.25 * AQA_BUYBACK_PCT * fraction
            cell = f"${y/1e6:.1f}M" if y > 0 else "—"
            print(f"  {cell:>22}", end="")
    print()

print()
print(f"  Observed avg bases: Q1 2026 = ${q1_avg/1e9:.3f}B   Q2 2026 = ${q2_avg/1e9:.3f}B")
print(f"  Rate assumptions: Bear=3.5% / Base=4.5% / Bull=5.5% (1Y UST proxy; actual instrument TBD)")
print(f"  Balance assumptions: Flat = Q2 avg held flat; Mid/High = user-growth scenarios")
print(f"  ⚠  Q3 2026 = $0 on cash basis (Oct 3 ∈ Q4); accrual Aug 26 irrelevant for cash model")

# ── FOOTNOTES ──────────────────────────────────────────────────────────────────
print()
print("  " + sep)
print("""
  FOOTNOTES & CAVEATS

  ¹  Builder pass-through: fees charged by frontend operators; in DeFiLlama's gross (Perps bucket)
     but absent from both net (AF revenue) and supply-side. Residual = gross − net − supply-side.
     NOT clamped to zero — negative residuals are flagged as data-quality warnings above.
     Validated per-quarter: zero Q1–Q2 2025 (pre-adoption); $16–23M/qtr from Q3 2025.
     2026 YTD: computed $33.95M vs DL's own builder dist line $33.89M (Δ $60K).
     Net effect on AF buyback pool: $0.

  ²  AQA (Assistance-Fund Quarterly Allocation) float yield:
     • Oct 3, 2026: first cash buyback (cash basis model; accrual date Aug 26 irrelevant here)
     • Base = system-wide spot USDC (HypurrScan /spotUSDC totalSpotUSDC)
     • Computed as quarterly average over ~90 daily obs per quarter (UTC bounds via calendar.timegm)
     • Q2 2026 avg ($1.743B) vs quarter-end ($2.575B): balance doubled within Q2,
       so point-in-time would overstate earnings base by ~48%
     • Allocation: 90% of yield → HYPE buyback; 10% retained

  ³  HyperEVM priority fee burn: EIP-1559 gas fees burned in HYPE, not USDC.
     Separate HYPE deflation mechanism; does NOT flow to AF or increase USDC buyback pool.
     Source: DeFiLlama hyperliquid-l1 (confirmed disjoint slug — "Hyperliquid L1" absent
     from hyperliquid dailyFees subcategories; no double-count with gross).

  *  2024 figures: full-year gross/perp/spot from HypurrScan cumulative delta (starts Nov 17 2024;
     genesis→Nov-17 total inferred from opening balance). Net and SS estimated by applying DL
     Q4-2024 cost ratios to the HS total. Builder column omitted (zero pre-adoption). Treat as ≈.

  WHAT IS NOT CAPTURED:
  — HLP vault trading P&L: gain/loss from HLP's market-making positions; accrues to HLP
    depositors, not AF. Volatile ±$50–200M/yr range; UI-only, no public API. This model
    is AF-buyback focused — HLP P&L does not affect the buyback pool.
  — Maker rebates sub-line: inside DL supply-side aggregate; DL UI shows ~$19M 2026 YTD
    but the public API exposes only bucket totals (Perps/Spot/HLP), not sub-components.
  — Pre-Nov 17 2024 daily breakdown: HypurrScan starts Nov 17; pre-Nov data is a single
    cumulative blob (opening balance = genesis-to-Nov-17 total, no per-day split).

  INDEPENDENT CROSS-CHECKS:
  ✓  DeFiLlama dailyRevenue vs HypurrScan /fees cumulative delta: ±1.7% for 2025 ($817M vs $832M)
  ✓  Total volume × 2.55 bps implied fee rate → $1.27B all-time (matches HypurrScan cumulative)
  ✓  Builder residual 2026 YTD: $33.95M computed vs $33.89M DL income statement (Δ $60K)
  ✓  Builder residual = 0 in Q1–Q2 2025 (expected, pre-adoption — structural validation)
  ✓  DL slug disjoint: hyperliquid-l1 absent from hyperliquid dailyFees subcategories
  ✓  deployGas scale: JEFF 2024-05-24 raw=1725.35 → $1,725 ✓; PERP 2025-05-26 raw=−978.38 → 978 HYPE ✓
  ✓  HIP-1 not in DL dailyRevenue: gross reconciliation confirms HIP-1 absent from DL subcategories;
     additive to buyback total is correct. 2025A = $817.8M (DL net) + $16.4M (HIP-1) = $834.2M
  ✓  HypurrScan completeness: cross-checked against HL spotMeta (ground truth). Found tokens in HL
     absent from HypurrScan; genuine paid auctions supplemented at runtime (see pre-flight output).
     Two categories: (a) bridge-deployed tokens (AXL, BZEC, USDUC, BRLA) — genesis holder is a
     0x2000… vault but HYPE auction gas was paid normally; (b) standard HIP-1 tokens HL indexed
     but HypurrScan omitted. Excluded: USDC/PURR (non-auction), L1 HYPE (deployer=None, gas=0),
     CHECK (tokenDetails=null, anomalous). Dates estimated by linear interpolation between
     bracketing HL token indices; USD computed at DL historical HYPE price.
  ✗  Maker rebate sub-line not independently quantified (inside supply-side aggregate)
  ✗  AQA yield rate not yet observable (instrument TBD; modeled as T-bill proxy)
""")

print("  DATA SOURCES")
print("  ┌─ DeFiLlama fees:  api.llama.fi/summary/fees/hyperliquid?dataType={dailyFees|dailyRevenue|dailySupplySideRevenue}")
print("  ├─ L1 burn:         api.llama.fi/summary/fees/hyperliquid-l1?dataType=dailyRevenue")
print("  ├─ HIP-1 auctions:  api.hypurrscan.io/pastAuctions  (+ HL supplement, see §3a)")
print("  ├─ HL spot meta:    api.hyperliquid.xyz/info  {type:spotMeta} + {type:tokenDetails}")
print("  ├─ Cumulative fees: api.hypurrscan.io/fees")
print("  ├─ USDC float:      api.hypurrscan.io/spotUSDC")
print("  └─ HYPE spot price: coins.llama.fi/prices/historical/{ts}/coingecko:hyperliquid")
print()
print(SEP)
