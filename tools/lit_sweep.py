#!/usr/bin/env python3
"""
lit_sweep.py -- the P4 diligence pass, as a script.

Two jobs, both from free APIs with no key and no login:

  venues  : enumerate FCCM / FPL / TRETS (or any dblp venue) for a year range
            and keep only titles matching the keyword list.        [dblp]
  cites   : forward-citation traversal -- every work citing a given paper,
            filtered the same way.                                 [OpenAlex]

WHY A SCRIPT. Claude cannot reach dblp.org or api.openalex.org from its
sandbox (fixed allowlist), and pasting whole proceedings into a chat exhausts
the context before anything gets read. This moves the bulk fetch to your
machine and returns only the filtered hits, which is the part that needs
judgement. It also satisfies the repo rule: the literature pass becomes
reproducible from a script rather than from someone's browsing session.

USAGE (stdlib only, no pip install):

    python tools/lit_sweep.py venues --from 2024 --to 2027
    python tools/lit_sweep.py cites --title "wordlength optimization"
    python tools/lit_sweep.py cites --openalex-id W2154687432

    # everything, written to a file to paste back:
    python tools/lit_sweep.py all > results/lit_sweep.txt

Output is compact TSV. Send the file; it should be a few dozen lines, not
a few thousand.
"""
import argparse, json, sys, time, urllib.parse, urllib.request

# Windows consoles default to cp1252, which cannot encode characters that
# appear routinely in paper titles (U+2212 minus, en dashes, accents), and
# the script dies mid-print. Force UTF-8 on stdout/stderr.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = {"User-Agent": "admm-wordlength-study/1.0 (academic literature sweep)"}

# Venue streams to enumerate. dblp stream keys.
VENUES = {
    "FCCM":  "streams/conf/fccm",
    "FPL":   "streams/conf/fpl",
    "TRETS": "streams/journals/trets",
    "FPGA":  "streams/conf/fpga",      # ACM FPGA -- same community
    "TCAD":  "streams/journals/tcad",  # where wordlength work often lands
}

# A title must contain at least one of these to be reported.
KEYWORDS = [
    "precision", "wordlength", "word-length", "word length",
    "fixed-point", "fixed point", "quantiz", "quantis",
    "admm", "proximal",
    # "optimization" alone floods TCAD with hundreds of unrelated hits, so it
    # is qualified. Add bare "optimization" back only for a targeted venue.
    "wordlength optim", "precision optim", "bit-width optim",
    "arithmetic", "bit-width", "bitwidth", "accuracy",
]

# Titles matching these are dropped even if they hit a keyword -- they are
# the dominant false positive in this community and would bury real hits.
NOISE = [
    "neural", "cnn", "dnn", "transformer", "llm", "deep learning",
    "genom", "blockchain", "graph neural",
]


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if i == tries - 1:
                print(f"# FETCH FAILED {url}\n#   {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))
    return None


def interesting(title):
    t = title.lower()
    if any(n in t for n in NOISE):
        return False
    return any(k in t for k in KEYWORDS)


def sweep_venues(y0, y1):
    print("=== DBLP VENUE SWEEP ===")
    print("venue\tyear\ttitle\tauthors\tdoi")
    seen = 0
    for name, stream in VENUES.items():
        first, page = 0, 1000
        while True:
            q = urllib.parse.quote(f"stream:{stream}:")
            url = (f"https://dblp.org/search/publ/api?q={q}"
                   f"&h={page}&f={first}&format=json")
            d = get(url)
            if not d:
                break
            hits = d.get("result", {}).get("hits", {})
            rows = hits.get("hit", [])
            if not rows:
                break
            for h in rows:
                info = h.get("info", {})
                try:
                    yr = int(info.get("year", 0))
                except ValueError:
                    continue
                if not (y0 <= yr <= y1):
                    continue
                title = (info.get("title") or "").strip()
                if not interesting(title):
                    continue
                au = info.get("authors", {}).get("author", [])
                if isinstance(au, dict):
                    au = [au]
                names = ", ".join(a.get("text", "") for a in au[:4])
                print(f"{name}\t{yr}\t{title}\t{names}\t{info.get('doi','')}")
                seen += 1
            if len(rows) < page:
                break
            first += page
            time.sleep(1)
    print(f"# {seen} venue hits in {y0}-{y1}")


def openalex_find(title):
    q = urllib.parse.quote(title)
    d = get(f"https://api.openalex.org/works?filter=title.search:{q}"
            f"&per-page=5")
    if not d:
        return None
    for w in d.get("results", []):
        print(f"# candidate: {w.get('id')}  {w.get('publication_year')}  "
              f"{w.get('title')}  (cited by {w.get('cited_by_count')})",
              file=sys.stderr)
    res = d.get("results", [])
    return res[0]["id"].rsplit("/", 1)[-1] if res else None


def sweep_cites(work_id, y0):
    """Every work citing work_id -- the traversal Scholar blocks.

    y0 defaults to 2005 here, NOT to the venue-sweep year. A 2003 paper's
    most important descendants are old: Jerez et al. 2013 (the primary prior
    art for this project) cites Constantinides 2003, and a >=2024 filter
    would exclude it by construction. A filter that cannot find the paper we
    already know about is not validated.

    Counts are reported by REASON. "0 kept" on its own cannot distinguish
    "nothing recent" from "the filter ate everything", and a silent zero is
    the failure mode that already cost us a day on the SAIF flow.
    """
    print(f"\n=== OPENALEX FORWARD CITATIONS of {work_id} (>= {y0}) ===")
    print("year\tvenue\ttitle\tdoi")
    cursor = "*"
    n_all = n_year = n_noise = n_nokey = kept = 0
    near_misses = []
    while cursor:
        url = (f"https://api.openalex.org/works?filter=cites:{work_id}"
               f"&per-page=200&cursor={cursor}")
        d = get(url)
        if not d:
            break
        for w in d.get("results", []):
            n_all += 1
            yr = w.get("publication_year") or 0
            title = (w.get("title") or "").strip()
            if yr < y0:
                n_year += 1
                continue
            t = title.lower()
            if any(nz in t for nz in NOISE):
                n_noise += 1
                near_misses.append((yr, title, "noise"))
                continue
            if not any(k in t for k in KEYWORDS):
                n_nokey += 1
                near_misses.append((yr, title, "no-keyword"))
                continue
            loc = (w.get("primary_location") or {}).get("source") or {}
            print(f"{yr}\t{loc.get('display_name','')}\t{title}\t"
                  f"{w.get('doi','')}")
            kept += 1
        cursor = d.get("meta", {}).get("next_cursor")
        time.sleep(1)
    print(f"# {kept} kept of {n_all} citing works "
          f"(dropped: {n_year} pre-{y0}, {n_noise} noise, {n_nokey} no-keyword)")
    if kept == 0 and n_all > 0:
        print("# ZERO KEPT -- showing 25 dropped titles so the filter can be")
        print("# judged rather than trusted:")
        for yr, t, why in sorted(near_misses, reverse=True)[:25]:
            print(f"#   [{why}] {yr}  {t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["venues", "cites", "all"])
    ap.add_argument("--from", dest="y0", type=int, default=2024,
                help="venue sweep start year")
    ap.add_argument("--cites-from", dest="cy0", type=int, default=2005,
                help="citation traversal start year; keep this EARLY, "
                     "a 2003 paper's key descendants are from the 2010s")
    ap.add_argument("--to", dest="y1", type=int, default=2027)
    ap.add_argument("--title", default="wordlength optimization")
    ap.add_argument("--openalex-id", default=None)
    a = ap.parse_args()

    if a.mode in ("venues", "all"):
        sweep_venues(a.y0, a.y1)
    if a.mode in ("cites", "all"):
        wid = a.openalex_id or openalex_find(a.title)
        if wid:
            sweep_cites(wid, a.cy0)
        else:
            print("# could not resolve a work id; pass --openalex-id",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
