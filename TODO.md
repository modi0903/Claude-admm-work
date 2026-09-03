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
- [x] Headline result — LUT −46.6%, power −30.4%, Fmax +20.7%
- [x] Negative result — asymmetry net-negative at two main widths
- [x] Sprint 1 generalisation — 24 cells, 4 ensembles, 2 sizes
- [x] Sprint 1b loop-gain model — resolvent mechanism, L2 0.031 bits
- [x] Related-work assessment vs Li et al. (TRETS 2023)
- [x] Supervisor deck (30 slides, ground-up + circuit level)

---

## P0 — critical path

- [ ] **L1 active-set term.** Loop-gain fit is 0.834 bits, outside the 0.5-bit
      criterion. d moves monotonically 0.00 → 0.70 with conditioning; add it as
      a second regressor and re-fit. If that closes it, the loop-gain model is
      complete for all three operators. — **C**, ~1 session
- [ ] **Lock the theorem set.** Once L1 closes: finalise which theorems are
      claimed, which are demoted (Theorem 5 → discussion), and which are
      rescoped (Theorem 2 → ill-conditioned regime only). — **C**, ~1 session

## P1 — measurement completeness (the bar Li et al. set)

- [ ] **SAIF power.** Post-route xsim writes SAIF, `report_power` consumes it.
      Replaces every vectorless estimate currently in STATUS.md, including the
      78 mW headline. No board needed. — **T**, ~2 h
- [ ] **Fmax sweep.** 20 ns was a loose target after the earlier timing
      failure. Tighten until failure per build; 71.1 MHz is not the ceiling.
      — **T**, ~2 h (scripted sweep, mostly waiting)
- [ ] **Throughput.** Cycles/iteration × iterations × period → solutions/s and
      LUTs·s/solution. Needed for any external comparison. — **C** derives the
      formula, **T** confirms cycle counts from simulation, ~1 h
- [ ] **Basys3 bring-up.** XDC, UART or ILA readback, validate against the
      golden model on hardware. Board is in the lab; `basys3_wrapper.v` exists;
      target part *is* the Basys3. — **T**, ~1 day
- [ ] **Measured wall power.** Needs the board and a meter. Report alongside
      the Vivado estimate, as Li et al. do. — **T**, ~2 h after bring-up

## P2 — scope justification

- [ ] **LASSO demonstration.** Reuses the whole stack; only the problem
      generator changes. Converts "proximal-operator scope" from an assertion
      into a demonstration, and tests whether the models transfer to a
      different data distribution. — **C**, ~1 session
- [ ] **Re-derive widths on the final configuration** and re-run the synthesis
      sweep once, so every number in the paper comes from one scripted pass.
      — **C** derives, **T** runs Vivado, ~1 session + 1 h

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

- [ ] **Proper related-work pass.** Google Scholar forward-citations on
      Constantinides 2003, plus FCCM / FPL / TRETS proceedings 2023–2026.
      Absence of search hits is not proof of novelty. — **T**, ~3 h
- [ ] Confirm FCCM 2027 dates when the CFP posts (current dates are
      extrapolated from 2026). — **T**, 5 min
- [ ] Fortnightly written update to supervisor, no reply required. — **T**

---

## Suggested sequencing

**Weeks 1–3.** P0 both items (C). In parallel: SAIF, Fmax, Basys3 bring-up (T).
These do not block each other.

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
