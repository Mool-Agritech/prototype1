# Finance Team — GCL Priority Tasks (deadline 25 Jul)

> Context: 3-min pitch video. Agroecology transition is the core pitch; parametric insurance is a supporting feature. The prototype/model is separate. Finance team needs to make the **unit economics and funding story coherent and defensible** — not exhaustive.

---

## The one-slide story to anchor everything

> Mool spends ~₹15,000/farmer over 8 years (APCNF benchmark) to transition a Vidarbha farmer off synthetic inputs and informal debt.  
> Parametric insurance covers the 15–20% yield dip during that transition.  
> The funder pays the premium. The farmer pays nothing. The farmer's net income rises 38–66%.  
> After year 5, carbon + offtake + data make the system self-funding.

Everything the finance team builds should ladder up to this.

---



## What to actually produce



### 1. Unit economics — one clean table

Build a single per-acre, per-season table. Rough numbers are fine — directional is what matters for a pitch.


| Line item                             | Estimate         | Source / assumption               |
| ------------------------------------- | ---------------- | --------------------------------- |
| Sum insured per acre (kharif)         | ₹18,000–25,000   | PMFBY Yavatmal cotton benchmark   |
| Trigger frequency (from our backtest) | ~44% of RC-years | Our model                         |
| Expected payout per triggered acre    | ₹3,000–6,000     | 10–25% of sum insured × frequency |
| Pure premium per acre                 | ~₹1,500–2,500    | Expected loss + risk margin       |
| Farmer pays                           | ₹0 (Phase 1)     | Funder-covered                    |
| Mool revenue per acre                 | ₹300–500         | Admin/margin slice                |
| Transition cost per farmer (8 yr)     | ₹15,000          | APCNF validated benchmark         |
| Net income gain per farmer            | +38–66%          | APCNF peer-reviewed outcomes      |


**Don't over-engineer this.** One table, one page.

---



### 2. Funding waterfall — who pays and when

Three sentences and a simple diagram is enough for the pitch.

- **Phase 1 (now):** Premium + transition costs funded by DFIs/foundations — POCRA II ($490M), NABARD Green Impact Fund (₹1,000 Cr), Azim Premji-type philanthropy. Farmer pays ₹0.
- **Phase 2 (2027–2029):** Blended finance — concessional loans (KfW model, results-based disbursement on verified farm conversions). FPOs contribute.
- **Phase 3 (2029+):** Carbon credits + certified offtake premium + data subscriptions make the system self-funding. Village-level SHG corpus takes over premium.

**Precedent to cite:** APCNF assembled ₹1,955 Cr this way — 36% govt grants, 41% KfW concessional loan, 14% philanthropy. We follow the same sequence.

---



### 3. One comparison vs PMFBY (for the demo segment)

Pull this directly from our backtest output. Finance team doesn't need to build this — just present it cleanly.


|                       | PMFBY                                             | Mool                                       |
| --------------------- | ------------------------------------------------- | ------------------------------------------ |
| 2023 drought coverage | ₹0 for ~62 RCs despite satellite-confirmed stress | Trigger fires automatically                |
| Time to payout        | 6–12 months                                       | < 72 hours                                 |
| Farmer action needed  | File claim                                        | None                                       |
| Covered by            | CCE crop-cutting (district average)               | Satellite threshold (revenue-circle level) |


---



### 4. Actuarial model — yes, build it

You have everything needed. Pull `data/processed/yavatmal_rc_model_ready_v2.csv` from the repo.

**Inputs from our backtest (already computed):**

- Loss frequency: 44% of RC-years have `rate_total > 10%`
- Loss severity distribution: `rate_total` column (0–54.7%, mean 8.8%) — fit a Beta or LogNormal
- Per-peril frequency: drought 35%, flood 56%, heat 0% (2021–2024 base)
- Trigger frequency (our satellite): 72% fire rate

**What to build:**

1. Fit a severity distribution to `rate_total` on the 169 loss events → get E[loss | loss occurs]
2. Pure premium = P(trigger fires) × E[loss severity] × sum insured per acre
3. Gross premium = pure premium × (1 + expense ratio ~25%) × (1 + profit margin ~10%)
4. Sensitivity table: how does premium change as payout cap varies (₹5k / ₹10k / ₹15k per acre)?
5. One stress test: if 2022 (worst year, 22% avg rate) happens 2 years in a row, does the premium still hold?

**Benchmark to check against:** PMFBY cotton kharif premium in Yavatmal is ~₹2,400/acre gross (farmer pays ~₹480, govt pays rest). Our gross premium should be in the same order of magnitude.

---



### 5. What NOT to do this week

- ❌ Don't model reinsurance structure
- ❌ Don't price carbon credits (treat as future upside, not base case)
- ❌ Don't negotiate with NBFCs — the loan embed is deprioritised
- ❌ Don't read the full PMFBY operational guidelines — only skim Section 13 (premium rates) and Section 7.2 (WBCIS parametric sub-scheme) for benchmark numbers

---

