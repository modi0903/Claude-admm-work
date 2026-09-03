"""
fxp_admm.py -- bit-exact software model of the RTL datapath.

Every primitive here mirrors one Verilog module one-for-one:
    q_narrow  <-> rtl/q_cast.v  q_narrow
    q_widen   <-> rtl/q_cast.v  q_widen
    sat_add   <-> rtl/q_cast.v  sat_add
    sat_shift <-> rtl/sat_shift.v
Python's >> on negative ints is a floor shift, identical to Verilog >>> on a
signed operand, so round-half-up is (v + 2^(sh-1)) >> sh in both.

This is the reference the testbench checks against and the model the BER /
convergence sweeps use. There is exactly one definition of the arithmetic.
"""
import numpy as np

INT_BITS = 2
F_MAIN, W_MAIN = 16, 18
F_BOX_ASYM, F_L2_ASYM = 8, 7
F_ACC, W_ACC = 32, 40


# ---------------------------------------------------------------- primitives
SAT_COUNT = [0]          # global saturation event counter -- never let a
                         # clipping floor masquerade as a quantization floor
                         # again. Any experiment that ends with SAT_COUNT > 0
                         # is measuring overflow, not wordlength.


def sat_reset():
    SAT_COUNT[0] = 0


def _sat(v, w):
    hi, lo = (1 << (w - 1)) - 1, -(1 << (w - 1))
    if v > hi:
        SAT_COUNT[0] += 1
        return hi
    if v < lo:
        SAT_COUNT[0] += 1
        return lo
    return v


def q_narrow(din, f_in, w_out, f_out):
    sh = f_in - f_out
    assert sh >= 0
    rnd = din + (1 << (sh - 1)) if sh > 0 else din
    return _sat(rnd >> sh, w_out)


def q_widen(din, f_in, f_out):
    return din << (f_out - f_in)


def sat_add(a, b, w=W_MAIN, sub=False):
    return _sat(a - b if sub else a + b, w)


def sat_shift(d, sh, w=W_MAIN):
    if sh > 0:
        return _sat(d << sh, w)
    if sh < 0:
        a = -sh
        return _sat((d + (1 << (a - 1))) >> a, w)
    return _sat(d, w)


def to_fx(x, f=F_MAIN, w=W_MAIN):
    return _sat(int(np.floor(np.asarray(x) * (1 << f) + 0.5)), w)


def to_fl(x, f=F_MAIN):
    return x / float(1 << f)


def vec_fx(v, f=F_MAIN, w=W_MAIN):
    return [to_fx(float(e), f, w) for e in np.asarray(v).ravel()]


def vec_fl(v, f=F_MAIN):
    return np.array([to_fl(e, f) for e in v])


# ------------------------------------------------------------- prox operators
class ProxConfig:
    """Constants are supplied as raw Q2.16 INTEGERS, identical to the RTL
    parameters. Never as floats: to_fx(0.667)=43713 but the RTL default is
    43691, and a 22-LSB constant mismatch masquerades as a datapath bug.

    f_l1 / f_box / f_l2 are the per-lane fractional widths. All lanes keep the
    same INT_BITS, so a narrowing cast is a pure round-off and can never
    overflow the integer field -- that is what makes the ordering argument
    clean and what makes these three numbers independently sweepable.
    """

    def __init__(self, asymmetric=True, f_l1=None, f_box=None, f_l2=None,
                 kappa_q16=6554, box_hi_q16=65536, box_lo_q16=-65536,
                 gamma_q16=43691):
        self.asym = asymmetric
        self.f_l1 = f_l1 if f_l1 is not None else F_MAIN
        self.f_box = f_box if f_box is not None else (F_BOX_ASYM if asymmetric else F_MAIN)
        self.f_l2 = f_l2 if f_l2 is not None else (F_L2_ASYM if asymmetric else F_MAIN)
        self.w_l1 = INT_BITS + self.f_l1
        self.w_box = INT_BITS + self.f_box
        self.w_l2 = INT_BITS + self.f_l2
        self.kappa = q_narrow(kappa_q16, F_MAIN, self.w_l1, self.f_l1)
        self.box_hi = q_narrow(box_hi_q16, F_MAIN, self.w_box, self.f_box)
        self.box_lo = q_narrow(box_lo_q16, F_MAIN, self.w_box, self.f_box)
        self.gamma = q_narrow(gamma_q16, F_MAIN, self.w_l2, self.f_l2)
        self.kappa_f = to_fl(kappa_q16)
        self.box_f = (to_fl(box_lo_q16), to_fl(box_hi_q16))
        self.gamma_f = to_fl(gamma_q16)


def prox_l1(v, c):
    vl = q_narrow(v, F_MAIN, c.w_l1, c.f_l1)
    lo = -(1 << (c.w_l1 - 1))
    a = (1 << (c.w_l1 - 1)) - 1 if vl == lo else abs(vl)
    m = max(a - c.kappa, 0)
    r = _sat(-m if vl < 0 else m, c.w_l1)
    return q_widen(r, c.f_l1, F_MAIN)


def prox_box(v, c):
    vb = q_narrow(v, F_MAIN, c.w_box, c.f_box)
    r = min(max(vb, c.box_lo), c.box_hi)
    return q_widen(r, c.f_box, F_MAIN)


def prox_l2(v, c):
    vl = q_narrow(v, F_MAIN, c.w_l2, c.f_l2)
    p = vl * c.gamma
    r = q_narrow(p, 2 * c.f_l2, c.w_l2, c.f_l2)
    return q_widen(r, c.f_l2, F_MAIN)


PROX = {0: prox_l1, 1: prox_box, 2: prox_l2}


# ------------------------------------------------------------- systolic array
def matvec_fx(M_fx, w_fx, n):
    """Q2.16 x Q2.16 -> Q4.32 products, exact accumulation in Q8.32, then
    round+saturate back to Q2.16. Overflow of the 40-bit accumulator is
    impossible by construction for |M|,|w| < 2 and n <= 32; asserted here."""
    out = []
    for i in range(n):
        acc = sum(M_fx[i * n + j] * w_fx[j] for j in range(n))
        assert abs(acc) < (1 << (W_ACC - 1)), "accumulator overflow: raise ACC_INT"
        out.append(q_narrow(acc, F_ACC, W_MAIN, F_MAIN))
    return out


# ------------------------------------------------------------------ full ADMM
def admm_fixed(M, q, mode, n, cfg, rho_shift=0, max_iter=64,
               eps_pri=None, eps_dual=None, trace=False):
    """Cycle-faithful fixed-point ADMM. Returns (z_fx, iters, history)."""
    M_fx = vec_fx(np.asarray(M).ravel())
    q_fx = vec_fx(q)
    z = [0] * n
    u = [0] * n
    zp = [0] * n
    hist = []
    ep = to_fx(eps_pri) if eps_pri is not None else 0
    ed = to_fx(eps_dual) if eps_dual is not None else 0

    for k in range(max_iter):
        w = [sat_add(q_fx[i], sat_shift(sat_add(z[i], u[i], sub=True), rho_shift))
             for i in range(n)]
        x = matvec_fx(M_fx, w, n)
        v = [sat_add(x[i], u[i]) for i in range(n)]
        zn = [PROX[mode](v[i], cfg) for i in range(n)]
        r = [sat_add(x[i], zn[i], sub=True) for i in range(n)]
        s = [sat_shift(sat_add(zn[i], z[i], sub=True), rho_shift) for i in range(n)]
        u = [sat_add(u[i], r[i]) for i in range(n)]
        zp, z = z, zn
        r_inf, s_inf = max(abs(e) for e in r), max(abs(e) for e in s)
        if trace:
            hist.append((k + 1, to_fl(r_inf), to_fl(s_inf), vec_fl(z)))
        if eps_pri is not None and r_inf <= ep and s_inf <= ed:
            return z, k + 1, hist
    return z, max_iter, hist


def admm_float(M, q, mode, n, kappa=0.10, box=(-1.0, 1.0), gamma=0.667,
               rho=1.0, max_iter=64, eps=1e-6, trace=False):
    M, q = np.asarray(M, float), np.asarray(q, float)
    z = np.zeros(n)
    u = np.zeros(n)
    hist = []
    for k in range(max_iter):
        x = M @ (q + rho * (z - u))
        v = x + u
        if mode == 0:
            zn = np.sign(v) * np.maximum(np.abs(v) - kappa, 0.0)
        elif mode == 1:
            zn = np.clip(v, box[0], box[1])
        else:
            zn = gamma * v
        r, s = x - zn, rho * (zn - z)
        u = u + r
        z = zn
        if trace:
            hist.append((k + 1, np.max(np.abs(r)), np.max(np.abs(s)), z.copy()))
        if np.max(np.abs(r)) <= eps and np.max(np.abs(s)) <= eps:
            return z, k + 1, hist
    return z, max_iter, hist
