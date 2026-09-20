#!/usr/bin/env python3
"""board_capture.py -- capture UART results from the Basys3 and diff them
against the golden vectors, so board evidence is a scripted comparison
rather than a photograph of some LEDs.

    pip install pyserial
    python tools/board_capture.py --port COM8 --op l1 --fmain 16

Start this BEFORE pressing btnC: the wrapper transmits once per press and
does not buffer.

Wire format: N lanes x 3 bytes, little-endian signed, then a 0x0A.

FRAMING NOTE. Do NOT read up to the 0x0A. The payload is binary and a data
byte can equal 0x0A -- lane 2 of z_l1_unif is 0x3060A, whose low byte is
exactly that -- which truncates the read at 6 bytes. Read a FIXED length and
treat the trailing byte as padding, not as a delimiter.
"""
import argparse, os, sys
try:
    import serial
except ImportError:
    sys.exit("pip install pyserial")

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--op", default="l1", choices=["l1", "box", "l2"])
ap.add_argument("--tag", default="unif")
ap.add_argument("--fmain", type=int, default=16)
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--solves", type=int, default=1)
ap.add_argument("--timeout", type=float, default=30.0,
                help="seconds to wait per solve -- press btnC within this")
a = ap.parse_args()

W = 2 + a.fmain                                    # INT_BITS + F_MAIN
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
gold_path = os.path.join(here, "tb", "vectors", f"z_{a.op}_{a.tag}.mem")
gold = [int(l.strip(), 16) for l in open(gold_path) if l.strip()]
gold = [g - (1 << W) if g >= (1 << (W - 1)) else g for g in gold]

NBYTES = a.n * 3
print(f"port {a.port}  op {a.op}  W={W}  golden {os.path.basename(gold_path)}")
print(f"waiting for {NBYTES} bytes -- press btnC now")

ser = serial.Serial(a.port, a.baud, timeout=a.timeout)
ser.reset_input_buffer()                           # drop anything stale
fails = 0
for s in range(a.solves):
    body = ser.read(NBYTES)                        # FIXED length, not delimited
    if len(body) != NBYTES:
        print(f"solve {s}: SHORT READ {len(body)} bytes, expected {NBYTES}")
        if body:
            print("   got:", body.hex(" "))
        fails += 1
        continue
    ser.read(1)                                    # consume the 0x0A padding
    got = [int.from_bytes(body[i*3:(i+1)*3], "little", signed=True)
           for i in range(a.n)]
    bad = [(i, g, h) for i, (g, h) in enumerate(zip(got, gold)) if g != h]
    if bad:
        fails += 1
        print(f"solve {s}: MISMATCH on {len(bad)} of {a.n} lanes")
        for i, g, h in bad[:8]:
            print(f"   lane {i}: board={g}  golden={h}  delta={g-h}")
    else:
        print(f"solve {s}: PASS  all {a.n} lanes bit-exact")
ser.close()
print(f"\n{a.solves - fails}/{a.solves} solves bit-exact")
sys.exit(1 if fails else 0)
