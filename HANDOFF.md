# HANDOFF — read this first

Entry point for a fresh conversation. Upload this file plus the repo; it
replaces the entire chat history.

## What this project is

A fixed-point wordlength study for ADMM hardware accelerators. Two analytic
models — one for error, one for fabric cost — validated against a bit-exact
software model and routed Artix-7 silicon.

Target: **FCCM 2027**, deadline ~mid-Jan 2027. Backups: FPL 2027 (~Mar),
IEEE TVLSI / TCAS-I (rolling). IEEE venues preferred (college sponsors them).

## The one rule

**No number enters the manuscript unless a script in this repo produces it.**
Every model claim gets a falsifier written and run *before* the claim is
drafted. Two of the main results are negative; this discipline is why they are
credible.

## Repo map

```
rtl/     admm_defs.vh q_cast.v sat_shift.v max_tree.v pe_mac.v
         systolic_array.v reconfigurable_prox.v admm_top.v
tb/      tb_admm_top.v + vectors/
model/   fxp_admm.py          bit-exact model, mirrors each RTL primitive
         gen_vectors.py       golden vectors at F_MAIN=16
         gen_vectors_fm.py    golden vectors at any F_MAIN
         experiments.py       wordlength / convergence / BER
         error_decomp.py      Theorem 1 falsifier
         annihilation.py      the (1-d) mechanism test
         lattice_rule.py      lattice design rule
         metric_check.py      NMSE vs absolute metric
         derive_widths.py     lane width derivation
         main_sweep.py        main-datapath sweep
         generalize.py        Sprint 1 generalisation
         loop_gain.py         Sprint 1b loop-gain model
syn/     run_ooc.tcl  harvest.tcl
```

Docs, in reading order: **TODO.md** (what to do next) → **STATUS.md** (all
measured results) → **THEORY_PLAN.md** (proofs, appendices A–D) →
**SPRINT1_RESULT.md** (latest experiments) → **RELATED_WORK.md** (novelty
position). SPRINT.md is superseded by TODO.md; keep it only for the venue
research.

## Verify in two minutes

```
build.bat 1          # Windows; or iverilog with files named explicitly
build.bat 0
```
Both must print `PASS: all lanes bit-exact vs golden model`.
Regression also passes at F_MAIN = 16, 12, 10, 9.

## Established results

**Error model (validated).** A proximal operator's precision requirement
follows from its *degenerate set* — the region where output does not depend on
input, where a perturbation is annihilated exactly. Effective noise scales with
(1−d), not the classical flat q²/12. Model/measured = 0.99 (L1), 1.00 (Box)
over d ∈ [0.12, 0.88]. Classical model wrong by 3–4× on average, 900× at
d = 0.999. At d = 1 measured error is exactly zero.

**Lattice rule (validated).** An operator constant not representable on its
lane's lattice costs exactly one bit. Measured 3.68–3.90× error penalty against
a predicted 4×; one bit through the closed loop, metric-independent.

**Cost model (silicon).** Fabric multiplier area is quadratic in operand width:
166 LUTs at 18×18, 35 at 9×9, ratio 4.74 (W² predicts 4.00). Profitability
condition: a(W²max − W²op) > cast overhead. The quadratic term exists only
while the multiplier is in fabric.

**Main result (silicon).** Q2.16 → Q2.9 across the whole datapath: LUTs
−46.6%, FFs −38.2%, carry −60.0%, power −30.4%, Fmax **+20.7%**. Every metric
improves at once.

**Negative result (silicon).** Per-operator asymmetric width allocation costs
area at both main widths tested (+192 LUTs at F=16, +144 at F=9). The
specialised lane is Box, which has no multiplier — no quadratic term to
harvest, only fixed cast overhead. Narrowing a multiplier-free lane is
unconditionally net-negative.

**Loop gain (latest).** Noise amplification through the ADMM loop is governed
by the resolvent ‖(I−T)⁻¹‖ of the linearised iteration map, into which the
prox enters as a gain g. With g = 1 the resolvent diverges (4 → 47,669) as
‖M‖₂ → 1; with g = 0.667 it *saturates at 3.18*. Contraction bounds the
resolvent independently of conditioning. Fits: L2 0.031 bits, Box 0.399, L1
0.834.

**Contraction lives at the loop, not the operator.** It does not reduce
operator-level precision needs — coefficient quantization dominates there — but
it buys up to five orders of magnitude of loop-level immunity. The original
theory put it at the operator and was wrong there.

## Claim set (see RELATED_WORK.md)

Primary: degenerate-set error model for non-smooth proximal operators.
Secondary: loop-gain/resolvent result; lattice rule; profitability condition.

**Do not claim:** "analytic derivation instead of search" (Li et al. TRETS 2023
and Constantinides 2003 both did it, for linear systems) or the DSP
operand-width threshold (Li et al. Fig. 14). Both are prior art. Li et al. is
the closest neighbour — read RELATED_WORK.md §3 before drafting related work,
and note their Table 4 (1.44 dB) independently supports our negative result.

## Open work

**See TODO.md** — the actionable checklist, with owners, effort and sequencing.
Critical path is the L1 active-set term in the loop-gain model (currently 0.834
bits, criterion is 0.5).

Bar set by Li et al.: measured board power, throughput, GOPS, energy, and a
comparison table. Not optional at this venue.

## Working context

Supervisor is on maternity leave and largely unavailable. Work is self-directed;
she remains a co-author and will need to sign off. Send a short written update
every two weeks that requires no reply.

## Traps already hit — do not repeat

- Part-selects of a localparam are **unsigned** in Verilog. Every comparison
  against a lane constant needs `$signed()`.
- Bit-slicing a constant to narrow it gives garbage (gamma 16384 → 9 bits = 0).
  Re-derive with rounding from the Q2.16 spec, using a fixed `SPEC_FRAC = 16`,
  not `F_MAIN`.
- Low-bit casts must keep MSBs and round, not take the low bits (that is a
  modulo wrap).
- Identical rows across different generics are always a bug, never a result.
  `harvest.tcl` now checks for this.
- Any experiment ending with `SAT_COUNT > 0` is measuring clipping, not
  quantization. Check it every time.
