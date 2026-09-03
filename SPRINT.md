# Sprint plan — target FCCM 2027

## Venue reality (checked Sept 2026)

| venue | deadline | status |
|---|---|---|
| FCCM 2026 | 17 Jan 2026 | passed |
| FPL 2026 | 3 Apr 2026 (final extension) | passed |
| **FCCM 2027** | **~mid-Jan 2027** (2026 pattern: abstract 10 Jan, paper 17 Jan) | **primary target, ~4.5 months** |
| FPL 2027 | ~late Mar 2027 | backup |
| TRETS | rolling | extended-version target |

FCCM takes 8-page long papers and 4-page short papers explicitly for "new
projects, early results, late breaking". If generalisation stays thin by
December, the short track is a legitimate choice, not a fallback.

Confirm FCCM 2027 dates when the CFP posts — the above is extrapolated.

## Literature threats — resolve before writing

| work | overlap | action |
|---|---|---|
| FAM fixed-point FPGA (TRETS, doi 10.1145/3567429) | **READ — see RELATED_WORK.md.** Closer than expected: analytic search-free bit allocation validated against exhaustive search, DSP threshold at 19→20 bits, and zero-error operations already exploited. | Two headline framings dropped. Novelty narrows to the non-smooth/degenerate-set model, the loop analysis, and the lattice rule. Their Table 4 FAM_M2 row (1.44 dB) independently supports our negative result. |
| SIRA: Scaled-Integer Range Analysis (AMD, 2025, arXiv 2508.21493) | Analytic range analysis for FPGA dataflow accelerators | Read. Position our range proposition (Prop 1) against it. |
| Constantinides et al. 2003, Wordlength Optimization for Linear DSP | The canonical reference | Already cited. Frame our work as the non-smooth/proximal counterpart to their linear analysis. |

**Revised claim set — see RELATED_WORK.md §5.** Primary claim is the
degenerate-set error model for non-smooth proximal operators. Secondary: error
analysis through a fixed-point iteration rather than a feed-forward pipeline,
the lattice rule, and the profitability condition. **Dropped as headlines:**
"analytic derivation instead of search" (Li et al. and Constantinides both did
it, for linear systems) and the DSP operand-width threshold (Li et al. Fig. 14).

A proper related-work pass is still owed — absence of search hits is not proof
of novelty.

## Hardware requirements

Target part `xc7a35tcpg236-1` **is the Basys3**. A `basys3_wrapper.v` already
exists in the tree.

| task | board needed? |
|---|---|
| SAIF-based power | No — post-route xsim writes SAIF, `report_power` consumes it |
| Fmax sweep | No |
| Throughput (cycles × period) | No |
| Generalisation sweeps | No |
| LASSO demonstration | No |
| Measured wall power vs estimate | **Yes** |
| On-board functional validation | **Yes** |
| FCCM Demo Night | **Yes** |
| Strongest artifact evaluation | **Yes** |

Verdict: strongly desirable, not blocking. FCCM rewards working hardware.
**Action in week 1: find out whether the lab has a Basys3.** If not, one costs
about $150 and the department has funding.

## Sprint 1 — weeks 1–3: close the credibility gaps

Ordered by what a reviewer attacks first.

1. **Generalisation.** The single biggest weakness. Currently one Gaussian
   channel, one operating point, N=8, real-valued.
   - 3+ problem ensembles (well-conditioned, ill-conditioned, correlated)
   - 2+ problem sizes (N=8, N=16 or 32)
   - Sweep across the κ / γ / ρ grid already built in `sweep_ordering.py`
   - Report the derived width for each, and whether the model predicts it
   - **Success criterion:** the error model predicts F* within ±1 bit across
     every configuration. If it does not, that is the finding and the paper
     changes again.
   - **Breadth bar:** Li et al. validate across three input signals (sine,
     square, DeepSig RADIOML). Match or exceed that, or the "you only tested
     one case" attack lands and they pre-empted it.
2. **SAIF power.** Replace every vectorless estimate. Testbench writes SAIF,
   post-route `report_power` consumes it. Regenerate all power numbers.
3. **Fmax sweep.** 20 ns was a loose target after the earlier failure. Tighten
   until failure, find the real ceiling for each build.
4. **Throughput.** Cycles per ADMM iteration × iterations × clock period →
   solutions/second and LUTs·s/solution. Needed for any external comparison.

**Bar set by Li et al.** They report measured board power, throughput in MS/s,
GOPS, energy in mJ, and a comparison against GPU and prior FPGA work, plus ACM
artifact badges. At TRETS/FCCM that is the standard, not a bonus. Items 2–4
above are not optional.

## Sprint 2 — weeks 4–6: second demonstration + positioning

5. **LASSO.** Justifies proximal-operator scope instead of asserting it.
   Reuses the entire existing stack — only the problem generator changes.
   Confirms the model transfers to a different data distribution.
6. **Read FAM and SIRA in full.** Write the differentiation paragraph before
   drafting anything else.
7. **Board bring-up** (if available). XDC, UART or ILA readback, on-board
   validation against the golden model, measured power.

## Sprint 3 — weeks 7–12: write

8. Draft to the FCCM 8-page structure. Theory is §III–IV, cost model §V,
   architecture §VI, results §VII.
9. Regenerate every figure and table from a single scripted pass.
10. Internal review, then supervisor sign-off with enough lead time.

## Working practice while supervision is light

- Send a short written update every two weeks: findings, decisions taken,
  nothing requiring a reply. Keeps her informed at near-zero cost and means the
  eventual co-author sign-off is not a cold ask.
- Do not schedule meetings that require preparation from her.
- Every decision taken alone gets recorded in STATUS.md with its evidence, so
  the reasoning is auditable later.

## The rule that does not change

No number enters the manuscript unless a script in this repository produces it.
