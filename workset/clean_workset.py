#!/usr/bin/env python3
"""Derive the v2 capsule workset from the approved v1 list (08_build_capsule_workset).

Why this exists (2026-09-04): the 40-volume capsule PILOT — the alphabetically
first 40 ids of v1 — returned `browning` as 72% of all bigram rows. The cause
was not the gunmaker: 14 of the 40 were scholarship on Robert and Elizabeth
Barrett Browning. A local audit of all 1,799 v1 rows showed why. 08 selects
books by a FIRM_NAMES title regex with no gun context (149 poet-Browning titles,
Frederic Remington the painter, Winchester MA / the Winchester Troper, Colt the
horse and the Colt Press) and selects serials with a bare `\\bhunting\\b` that
admitted a tuberculosis journal, a horse-show weekly and a real-estate guide.
It also never dedupes library copies (1,799 rows, 1,081 distinct titles).

This script is a REPLAYABLE, AUDITABLE transformation of v1 -> v2. It does NOT
re-select from the hathifile; every v2 id is a v1 id, so v2 stays inside the
workset HTRC approved ("~1,800 in-copyright volumes: sporting periodicals,
sporting-goods trade press, firearms monographs, 1929-1980") -- just fewer of
them. The removal ledger names the reason for every dropped row.

GOVERNING PRINCIPLE -- be INCLUSIVE at the capsule stage. After the HTRC
sunset (2026-09-30) nothing can be re-downloaded. So we remove only the
clearly off-topic, KEEP every library copy of a serial volume and every
fiction title (tier-flagged from EF MARC genre), and leave dedup/scope
decisions to analysis time, where the exported per-volume rows can be joined
back to this file's `tier`, `ef_genre` and `description` columns.

Serials are NOT deduped by volume number: bound halves of a periodical share
a `v.N` (American Rifleman 53 -> 20 under that rule was a mistake). The only
safe duplicate key is (title, year, description), which finds 1 copy.

Outputs (CORPUS_DIR, --apply):
  capsule_workset_v2.csv          htid, year, bib_fmt, stratum, tier, ef_genre,
                                  title, description
  capsule_htids_v2.txt            the id list `htrc download` takes
  capsule_workset_v2_removed.csv  every v1 row not carried, with `reason`
Dry-run (default) prints the summary and writes nothing.
"""
import argparse
import bz2
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hathi_common import CORPUS_DIR, EF_DIR, id_to_ef_path

# Serial title prefixes (normalised) admitted by 08's bare `hunting` pattern
# that are not sporting/arms periodicals.
OFF_SERIAL_PREFIXES = [
    "the rider driver",                 # horse-show weekly
    "journal of the outdoor life",      # National Tuberculosis Assn. journal
    "suburban detroit",                 # real-estate "home hunters guide"
    "international fox hunters",        # stud book
    "accommodations for hunters",       # state tourism pamphlet
    "compilation of laws",              # state regulations
    "archery deer hunting",
    "campground guide",
    "indiana hunting and trapping",
    "manual for the issuance",
    "status of wildlife",
]
# Kept but BORDERLINE (state conservation / game-breeding magazines) --
# scope them at analysis time: "kentucky happy hunting ground",
# "modern game breeding and hunting club news".

# A firearm word in the title keeps a book on its own.
GUNWORD = re.compile(
    r"\b(?:guns?|rifles?|shotguns?|firearms?|pistols?|revolvers?|handguns?|"
    r"ammunition|gunsmith\w*|gunmak\w*|musket\w*|carbine\w*)\b", re.I)
# A brand name keeps a book only WITH gun context somewhere in the title.
BRANDS = ["browning", "colt", "remington", "marlin", "winchester", "savage",
          "stevens", "ithaca", "springfield", "mossberg", "ruger", "luger",
          "mauser", "wesson", "yale"]
BRAND = re.compile(r"\b(?:" + "|".join(BRANDS) + r")(?:'s)?\b", re.I)
GUNCTX = re.compile(
    r"\b(?:guns?|rifles?|shotguns?|firearms?|pistols?|revolvers?|handguns?|arms|"
    r"armed|ammunition|cartridges?|carbines?|muskets?|shoot(?:ing|er|ers)?|"
    r"marksman(?:ship)?|sporting|hunt(?:ing|er|ers)?|catalog(?:ue)?s?|repeating|"
    r"automatic|cali?bre|ordnance|armou?ry|gunsmith(?:ing|s)?|gunmak\w*|trap|"
    r"skeet|ballistics?|reload(?:ing)?|sidearms?|weapons?|gunn?ery|small arms|"
    r"collector'?s?|shells?|gauge|magnum)\b", re.I)
# Gun-word titles that are not about guns.
EXCLUDE = re.compile(
    r"electron[- ]gun|electron beam|velocity-modulated|"   # physics
    r"gun kessle|jung[- ]gun|gun[- ]kim\b", re.I)          # personal names
# Recall check on the dropped set (43 brand+history titles read by hand)
# found exactly one real gun book; carried by title.
INCLUDE_TITLES = [re.compile(r"^the modern colt guide", re.I)]


def norm(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(t).lower()).split())[:60]


def ef_genre(htid: str) -> str:
    """Comma-joined MARC genre codes from the volume's EF file ('' if absent)."""
    try:
        with bz2.open(EF_DIR / id_to_ef_path(htid), "rt", encoding="utf-8") as f:
            g = json.load(f).get("metadata", {}).get("genre")
    except Exception:
        return ""
    g = g if isinstance(g, list) else ([g] if g else [])
    return ",".join(str(x).rsplit("/", 1)[-1] for x in g)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the v2 files")
    args = ap.parse_args()

    v1 = pd.read_csv(CORPUS_DIR / "capsule_workset.csv", dtype=str).fillna("")
    v1["ntitle"] = v1.title.map(norm)
    reason = pd.Series("", index=v1.index)

    # ---- serials --------------------------------------------------------
    ser = v1[v1.stratum == "serial"]
    off = ser.ntitle.map(lambda t: any(t.startswith(p) for p in OFF_SERIAL_PREFIXES))
    reason[ser.index[off]] = "serial: off-topic title (bare 'hunting' match)"
    kept_ser = ser[~off]
    dup = kept_ser.duplicated(["ntitle", "year", "description"], keep="first")
    reason[kept_ser.index[dup]] = "serial: duplicate library copy (same title/year/enumeration)"

    # ---- books ----------------------------------------------------------
    bk = v1[v1.stratum == "book"]
    t = bk.title
    include = t.map(lambda s: any(p.search(s) for p in INCLUDE_TITLES))
    excl = t.str.contains(EXCLUDE) & ~include
    keep = (t.str.contains(GUNWORD) | (t.str.contains(BRAND) & t.str.contains(GUNCTX)))
    keep = (keep & ~excl) | include
    brand_only = t.str.contains(BRAND) & ~t.str.contains(GUNCTX) & ~keep
    reason[bk.index[excl]] = "book: gun word is physics or a personal name"
    reason[bk.index[brand_only]] = "book: brand name with no gun context (poet/painter/place/horse)"
    rest = bk.index[~keep & ~excl & ~brand_only]
    reason[rest] = "book: no firearm word or gun-context brand in title"

    v2 = v1[reason == ""].copy()
    removed = v1[reason != ""].assign(reason=reason[reason != ""])

    # ---- tiers (books only; EF MARC genre) ------------------------------
    v2["ef_genre"] = ""
    is_bk = v2.stratum == "book"
    v2.loc[is_bk, "ef_genre"] = v2.loc[is_bk, "htid"].map(ef_genre)
    def tier(r):
        if r.stratum == "serial":
            return "serial"
        codes = r.ef_genre.split(",")
        return "book_fiction" if "fic" in codes else ("book" if r.ef_genre else "book_unknown_genre")
    v2["tier"] = v2.apply(tier, axis=1)
    v2 = v2.sort_values(["stratum", "title", "year"])

    cols = ["htid", "year", "bib_fmt", "stratum", "tier", "ef_genre", "title", "description"]
    print(f"v1 {len(v1):,} -> v2 {len(v2):,}  (removed {len(removed):,})")
    print("tiers:", v2.tier.value_counts().to_dict())
    print("removal reasons:")
    print(removed.reason.value_counts().to_string())
    if not args.apply:
        print("\n(dry run; --apply writes capsule_workset_v2.csv / capsule_htids_v2.txt / "
              "capsule_workset_v2_removed.csv)")
        return
    v2[cols].to_csv(CORPUS_DIR / "capsule_workset_v2.csv", index=False)
    (CORPUS_DIR / "capsule_htids_v2.txt").write_text("\n".join(v2.htid) + "\n")
    removed[["htid", "year", "stratum", "title", "reason"]].to_csv(
        CORPUS_DIR / "capsule_workset_v2_removed.csv", index=False)
    print(f"\nwrote {CORPUS_DIR / 'capsule_workset_v2.csv'} + capsule_htids_v2.txt + "
          f"capsule_workset_v2_removed.csv")


if __name__ == "__main__":
    main()
