# TODO

Single source of truth for what is done and what is left.
Owner **T** = Tanmay (needs Vivado, the board, or a judgement call).
Owner **C** = Claude (model, analysis, RTL, writing).

Target: FCCM 2027, ~mid-Jan 2027. Roughly 19 weeks from 3 Sept 2026.

---

## DONE

- [x] RTL rebuilt, parameterised, 8 bugs fixed (STATUS.md)
- [x] Bit-exact golden model; regression passes at F_MAIN = 16, 12, 10, 9
- [x] Theorem 1 falsifier — annihilation validated, 0.99 / 1.00 (Appendix A)
- [x] Lattice rule — derived, then measured at exactly 1 bit (Appendix B)
- [x] Cost model fitted on silicon — 166 / 35 LUTs, ratio 4.74
- [x] Six-build synthesis sweep, all valid, duplicate-row check added
- [x] Main-datapath sweep — Q2.9 is the design point (Appendix D)
- [x] Headline result — LUT −46.6%; power/Fmax SUPERSEDED by measurement
      (now dynamic −36%, Fmax +28.8%, energy/solve −36%). See STATUS.md.
- [x] Negative result — asymmetry net-negative at two main widths
- [x] Sprint 1 generalisation — 24 cells, 4 ensembles, 2 sizes
- [x] Sprint 1b loop-gain model — resolvent mechanism, L2 0.031 bits
- [x] Related-work assessment vs Li et al. (TRETS 2023)
- [x] Supervisor deck (30 slides, ground-up + circuit level)
- [x] ~~**P0.1 L1 active-set term** (2026-09-04) — d closes it.~~ **RETRACTED 2026-09-20: fails held-out seeds (1.38 bits); see THEOREM_LOCK.** LOO 0.928 → 0.340
      bits; Box 0.513 → 0.234. Survived the confound test: log(cond) alone
      gives LOO 1.237, worse than baseline, so d is not a conditioning proxy
      despite corr²(d, log cond) = 0.94. `model/loop_gain_l1.py`.
- [x] **P1 SAIF power** (2026-09-04) — uniform18 11 mW / main9_uniform 7 mW
      dynamic, both Confidence High, 74% / 72% nets matched. Vectorless
      figures were ~10× high. Static 68 mW dominates, so TOTAL power falls
      only 5.0%; the claim must say DYNAMIC.
- [x] **P1 Fmax sweep** (2026-09-04) — 66.3 / 85.4 MHz measured by constraint
      binary search. +28.8% (bracket +27.6% to +30.4%), superseding +20.7%.
      LUTs at each build's own Fmax match the 20 ns builds, so area and speed
      are the same design points.
- [x] **P1 Throughput** (2026-09-04) — cycles = 26×iterations + 3, IDENTICAL
      across both builds. Energy/solve 184 → 117 nJ, −36%, frequency-
      independent. Lead with this figure.
- [x] **Comparison table vs prior accelerators** (2026-09-20) — COMPARISON.md
- [x] **LASSO second problem** (2026-09-20) — see P2 and THEOREM_LOCK.
- [x] Gate-level SAIF/Fmax infrastructure: `tb/tb_admm_top_gl.v`,
      `syn/saif_power.{bat,tcl}`, `syn/saif_log.tcl`, `syn/fmax_sweep.tcl`.

---

## P0 — critical path

- [x] ~~L1 active-set term~~ CLOSED 2026-09-04 (see DONE).
- [x] ~~**P0.2a — Box functional form and the sign flip.**~~ CLOSED 2026-09-04,
      see `P0_RESULT.md`. Churn mechanism REFUTED (2 of 3 predictions fail;
      Box churns MORE than L1 and both are ~frozen). Sign flip explained by
      d's opposite monotonicity with conditioning, not by mechanism. Box form
      is d² (paired t=2.56, p<0.05); operators do NOT share a form. The
      loop-gain model is therefore EMPIRICAL, one term per operator.
<details><summary>original P0.2a text</summary>

      The d coefficient is
      +20.6 for L1 and −20.4 for Box. Same regressor, opposite directions.
      Plausible story: L1's degenerate set is threshold-zeroing (churns,
      destabilising), Box's is clipping (freezes, stabilising — consistent
      with Sprint 1's finding). That is a STORY, not a test. Also Box's best
      form is d² (LOO 0.178) not d (0.234), so the Box form is unsettled.
      Needs a falsifier that can distinguish churn from freezing before
      either form is claimed. — **C**, ~1 session
</details>
- [x] ~~**P0.2b — Lock the theorem set.**~~ DONE 2026-09-04, see
      `THEOREM_LOCK.md`. T1 + Prop1 + T4 claimed; loop-gain claimed as
      empirical; T2 and T5 demoted to discussion; **T3 blocked** — its
      held-out-width falsifier was never run, and the model is currently
      fitted and reported on the same points, which violates the repo rule.
- [x] **T3 held-out width test — DONE 2026-09-20** (`model/lane_area.py`).
      Fit on W = 16/10/9 (lanes = F_MAIN, no cast), predict lane 8: **-6.3%**
      on the matched-cast build, -10.4% on the deeper-cast one. Inside the 10%
      bar; cost model unblocked. Slice LUTs; on cells b = 26.4 and -15.5%.
- [x] **T2 crossover sweep — DONE 2026-09-20** (`model/t2_crossover.py`).
      Headline HOLDS (Box-L2 crosses between cond 10 and 20). Stated mechanism
      FAILS (operator-only: signs 2/8 and 0/14). Restated with the loop
      resolvent, zero fitted parameters: Box-L2 0.288 bits, 8/8. Earlier
      "measurement contradicts T2" was wrong -- corrected in THEOREM_LOCK.
- [x] **Test the kappa-quantisation term for L1** — DONE, REFUTED (and the
      outlier explanation too). L1-Box residual is OPEN. `model/kappa_term.py`. ~~(Corollary 1a). The T2
      predictor under-predicts L1-Box by 0.4-0.6 bits and is flat in kappa
      while the measurement is not. — **C**, ~1 session~~
- [~] superseded original P0.2b text: NOW UNBLOCKED. P0_RESULT.md fixes what
      may and may not be claimed: loop-gain is empirical with a per-operator
      term; no mechanism for the sign; Theorem 1's (1-d) stays derived.
      Finalise which theorems are claimed,
      demoted (Theorem 5 → discussion; Sprint 1's 2.509-bit failure is the
      evidence), and rescoped (Theorem 2 → ill-conditioned regime only).
      — **C**, ~1 session

## P1 — measurement completeness (the bar Li et al. set)

- [x] ~~SAIF power~~ / ~~Fmax sweep~~ / ~~Throughput~~ CLOSED for the two
      headline builds 2026-09-04 (see DONE). Residual work below.
- [x] ~~Rescue or drop Result 1's power row~~ RESOLVED 2026-09-04: **REFUTED**.
      Measured 11 mW dynamic for BOTH uniform_nodsp and asym_nodsp. The 18.8%
      reduction was an artefact of two vectorless estimates. Row struck in
      STATUS.md; the negative result is now consistent across area and power.
- [x] ~~**Other four builds still carry vectorless power and extrapolated Fmax**~~
      DONE 2026-09-04: all six builds swept (fmax_all.log). Asymmetry penalty
      confirmed at +4.3% LUT at BOTH widths; F_MAIN shown to dominate lane
      width on both area and frequency. See STATUS.md.
- [ ] ~~superseded~~ old text:
      (uniform10, asym_derived, main10_uniform, main9_asym). Either measure
      them or mark those columns unquotable in the paper. — **T**, ~2 h if all
- [x] **Basys3 bring-up — DONE 2026-09-17.** uniform18 and main9_uniform, all
      three operators, bit-exact vs golden over UART. Four wrapper bugs found
      and fixed (see BOARD.md).
- [x] **Board session 2 — DONE 2026-10-03.** LASSO bit-exact on silicon
      (3 instances); main9 bit-exact at 82.5 MHz and uniform18 at 65 MHz,
      timing met in context; speed-up +26.9% in context vs +28.8% OOC,
      brackets overlap. Session-1 divider builds found never to have met
      timing -- superseded. See BOARD.md / STATUS.md.
      ~~**Board session 2 (2026-10-03): LASSO on silicon + at-speed in
      context.** Three scripted builds (`syn/board_build.tcl`), plan and
      commands in BOARD.md. Closes: LASSO only ever simulated; board only ever
      at 50 MHz while the paper quotes 85.4 MHz OOC. — **T** runs, **C**
      folds results into BOARD/STATUS/paper.~~
- [~] **Measured wall power — DROPPED 2026-09-20** (T's call, instrumentation
      not available). The build-to-build delta is ~4 mW, below what a USB
      meter resolves. SAIF power stands as the measured figure; the paper says
      "post-route, activity-annotated" and claims nothing about wall power.
      Reopen only if a bench supply or a ≤1 mA meter appears.

## P1b — discovered during measurement, not previously tracked

- [x] **Gate-level flow committed + `syn/README.md`** (2026-09-20): run order
      and all seven traps, including `-debug typical` and the `-generic_top`
      SAIF corruption.
- [x] **Iteration count — DECIDED 2026-09-20.** Every throughput/power/energy
      figure is quoted at FIXED K=32 via cycles = 26K+3 (identical across
      builds). Per-build iteration counts appear only as termination
      behaviour, with the `box_unif` MAX_ITER truncation stated. See STATUS
      "PRE-DRAFT AUDIT".
- [x] **Checkpoint/script drift — AUDITED 2026-09-20.** Only `asym_nodsp` is
      genuinely unbuildable; `uniform_nodsp` is a superseded name for
      `uniform18`, the `*_dsp` pair is the USE_DSP_L2=1 discussion only, and
      the rest are quoted nowhere. Asymmetry power null now rests on **two
      rebuildable pairs** (`tools/power_table.py`), with the legacy pair as
      corroboration.
- [x] **Power rounding — DECIDED.** Draft quotes absolutes (11/7 mW) and
      energy per solve (184/117 nJ); any percentage carries its 29–44% bound.
      `tools/power_table.py` prints the rounding note with every table.
      — **C**, at drafting time

## P2 — scope justification

- [x] **LASSO demonstration** (2026-09-20). 4 registered predictions:
      P-L1 T1 0.981–1.028 at native d 0.62–0.77 PASS; P-L2 F*: m=32 → 8,
      m=16 → 9, m≤8 → 9–11 PASS; **P-L3 support ≥99% FAILED** (90–100%;
      post-hoc: all 11 mismatches ≤2 LSB); P-L4 RTL bit-exact at F=16 and 9
      PASS. THEOREM_LOCK "SECOND PROBLEM". Optional: board run at F=9
      (BOARD.md, "LASSO on the board").
- [x] **Comparison table against prior accelerators** (2026-09-20).
      `COMPARISON.md`, `tools/comparison_table.py`, `data/comparison_lit.json`,
      paper Sect. "Comparison with prior accelerators". 8 prior works, each
      with a URL and a verification record. All three
      outstanding papers were obtained and read 2026-09-20: AccelMPC
      (arXiv:2609.09380) and Peccin (TLA 2020) are now rows, Escarate
      (ICA-ACCA 2022) is cited but not tabulated (times only). Fairness
      decisions are written out in COMPARISON.md and in the paper. Lane-area slope re-checked on both LUT metrics
      (`model/lane_area.py`): 19.6 Slice LUT/bit stands, cells give 26.4 and a
      worse held-out miss. Headline stays −46.6% (cells) with −44.9% (Slice
      LUTs) stated beside it; both come from the same checkpoints.
- [x] **Model-side pass — DONE 2026-10-03** (`tools/model_pass.py`). Every
      analysis script rerun from scratch in dependency order: 41 committed
      outputs (all results/*.json + golden vectors) reproduce EXACTLY. F* = 9
      re-derived. Printed-only numbers now stored in results/model_pass/.
- [ ] **Synthesis-side check** — **T**, ~40 min unattended:
      `vivado -mode batch -source syn/run_ooc.tcl -nojournal -log results/syn/run_ooc_pass.log`
      then `python tools/syn_pass_check.py`. If all seven builds reproduce
      exactly (Vivado is already shown deterministic here: two full Fmax
      sweeps identical), the hardware numbers stand and no 8-hour re-sweep is
      needed. Any drift -> full pass before drafting.

## P3 — writing

- [ ] Related-work section, written for the Sydney group (likely reviewers).
      Get RELATED_WORK.md §3 stated early and precisely. — **C**
- [ ] Draft to FCCM 8-page structure: theory §III–IV, cost model §V,
      architecture §VI, results §VII. — **C**
- [ ] Regenerate every figure and table from a single scripted pass. — **C**
- [ ] Artifact packaging (Li et al. have three ACM badges; repo is already
      close). — **C** + **T**
- [ ] Supervisor sign-off, with lead time. — **T**

## P4 — owed diligence

- [x] **Related-work pass — DISCHARGED 2026-09-06.** See RELATED_WORK.md.
      Scripted (`tools/lit_sweep.py`), reproducible, raw output committed.
      **No collision.** Kinsman & Nicolici TCAD 2011 (CG bit-width allocation)
      is the closest prior art and has 16 citations in 15 years, NONE extending
      it to iterative optimisation solvers; the lineage went to range/overflow
      analysis instead. Three prior-art quotes now define our contribution.
      **NEW BLOCKING ITEM below.** Residual: 5 of Kinsman's 16 citing works
      dropped as no-keyword, uninspected.
- [x] ~~**ANSWER THE ADVERSARIAL-CASE THREAT.**~~ DONE 2026-09-06 via
      `model/adversarial.py`. **The model UNDER-predicts per-instance**, and
      random right-hand sides already break it (L1 +7.58 bits; adversarial
      +11.43). Root cause: loop_gain.py fits 20-trial ENSEMBLE AVERAGES, so the
      published bit figures are ensemble-level. Resolution: SCOPE the claim (a
      guaranteed bound would mean competing with Jerez/Kinsman on their ground
      with their conservatism). See THEOREM_LOCK.md.
- [x] **Relabel every loop-gain bit figure** — DONE 2026-09-20, and it went
      further than a relabel: the held-out test retracted the L1/Box fits.
      ~~in STATUS/THEORY_PLAN as "ensemble
      mean over N trials at fixed conditioning". Currently they read as if they
      were per-instance. — **C**, ~30 min~~
- [x] **Quote a per-instance margin** — DONE: L2 +1 bit covers p99 (+0.66);
      none quotable for L1/Box (their fits don't generalise). ~~for wordlength selection, derived from
      the measured under-prediction, or state that per-instance safety requires
      the prior art's bounds. — **C**, at drafting~~
- [~] superseded: **ANSWER THE ADVERSARIAL-CASE THREAT.** Kinsman & Nicolici Sect. V-D-4
      breaks a Monte-Carlo-validated CG design with an adversarial b (error
      ~35 sigma beyond simulated worst case; double precision also fails).
      Our model is validated over RANDOM conditioning sweeps. Either produce a
      worst-case result or scope the claim explicitly as predictive
      in-distribution, NOT a robustness bound. A reviewer WILL ask.
      — **C**, ~1 session, before drafting Sect. III
- [~] ~~superseded~~ **Related-work pass — PARTIAL, 2026-09-04.** See RELATED_WORK.md. Found
      the primary prior art (Jerez/Constantinides et al., fixed-point ADMM on
      FPGA with wordlength selection) and read Wu et al. 2022 in full. Li et
      al. TRETS 2023 citation resolved and NOT paywalled (artifact repo +
      open-access USyd thesis).
      **STILL OWED**, this does not discharge the item:
        - Google Scholar forward-citation traversal on Constantinides 2003.
          Jerez was found by SUBJECT search, not traversal, so the traversal
          may surface more. Scholar is not machine-accessible to Claude.
        - Systematic FCCM / FPL / TRETS 2024–2027 sweep via IEEE Xplore and
          ACM DL. Everything found so far came via secondary citation.
        - ~~Hamadouche arXiv:2210.02094 and 2203.02204~~ READ 2026-09-20,
          no collision (RELATED_WORK). Re-verify the quoted sentences against
          the PDFs before submission -- they came via a fetch summariser.
        - Li et al. SQNR derivation — their <1 dB (~0.17 bit) bar is ~3x
          tighter than our 0.5-bit criterion, which must be justified.
      Absence of search hits is not proof of novelty. — **T**, ~3 h remaining
- [ ] Confirm FCCM 2027 dates when the CFP posts (checked 2026-09-20: not yet
      up; FCCM 2026 was abstract 10 Jan / paper 17 Jan, no extensions,
      notification 16 Mar, ≤8 pp excl. refs. DATE 2027 closed 20 Sep 2026 —
      6 pp, double-blind, missed. FPL 2027 ≈ late Mar 2027, ≤8 pp + refs.
      TCAS-I rolling, ≤14 pp incl. refs/bios, single-blind, page charges
      above 11 pp.) FCCM 2026 ran abstract
      10 Jan / paper 17 Jan / notification 16 Mar, held 13–16 May in Atlanta,
      which supports the mid-Jan estimate. **If the current date is past
      Jan 2027, this deadline has gone and the venue decision reopens — FPL
      or TVLSI/TCAS-I become the live targets.** — **T**, 5 min
- [ ] Fortnightly written update to supervisor, no reply required. — **T**

---

## Suggested sequencing

**Week 1 (revised 2026-09-04).** P0.1, SAIF, Fmax and throughput all closed on
day 2 — ahead of plan. Remaining week-1 work:
  - **C**: P0.2a (Box form / sign flip), then P0.2b (lock theorems).
  - **T**: Result 1 power rescue (~40 min, highest value per minute — it either
    saves a published claim or removes a wrong one), then re-scope Basys3 now
    that the wrapper is known missing.

**Weeks 2–3.** Original plan: remaining P1 measurement, Basys3 bring-up (T);
P1b housekeeping and LASSO start (C).

**Weeks 4–6.** LASSO + width re-derivation (C). Measured power + throughput (T).
Related-work pass (T).

**Weeks 7–14.** Writing. Final synthesis pass early in this window so no number
changes after drafting starts.

**Weeks 15–19.** Internal review, artifact packaging, supervisor sign-off,
buffer. Do not let the buffer shrink — the last two reframes both came from
experiments run late.

---

## Decision log — things settled, do not relitigate

| decision | rationale |
|---|---|
| Venue: FCCM 2027 | IEEE, best topical fit, artifact track, ~19 weeks |
| Not ISCAS 2027 (13 Oct) | 6 weeks; would split the contribution |
| Scope: proximal-operator ADMM datapaths, not MIMO | MIMO framing obliges competing on detector throughput, which is not the contribution |
| Uniform Q2.9, not asymmetric | asymmetry measured net-negative twice |
| Drop "analytic vs search" as a headline | prior art (Li et al., Constantinides) |
| Drop the DSP-threshold claim | prior art (Li et al. Fig. 14) |
