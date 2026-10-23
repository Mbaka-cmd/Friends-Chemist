import re
import shutil
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.models import Product

EXT = {".jpg", ".jpeg", ".png", ".webp"}
SYN = {"syp": "syrup", "susp": "suspension", "inj": "injection", "tabs": "tablets", "tab": "tablets",
       "gen": "generic", "caps": "capsules", "cap": "capsules", "pess": "pessaries",
       "exp": "expectorant", "paed": "paediatric", "paeds": "paediatric",
       "gms": "g", "gm": "g", "litre": "l", "litres": "l"}
STOP = {"bp", "b", "p", "of", "the", "with", "for", "and", "per", "piece", "pcs", "nil", "cold"}
UNIT_RE = re.compile(r"^(\d+(?:\.\d+)?)(mg|mcg|ml|g|kg|l|s|cc|iu|%)$")
DIM = {"mg": ("w", 1.0), "g": ("w", 1000.0), "kg": ("w", 1e6), "mcg": ("w", 0.001),
       "ml": ("v", 1.0), "l": ("v", 1000.0), "cc": ("v", 1.0), "s": ("n", 1.0),
       "iu": ("iu", 1.0), "%": ("p", 1.0)}
OK_MIN, REVIEW_MIN, TIE_GAP = 0.85, 0.60, 0.03


def norm(s):
    s = re.sub(r"\.(jpe?g|png|webp)$", "", s, flags=re.I).lower()
    s = s.replace("&", " ").replace("_", " ")
    s = re.sub(r"(\d)\s+(\d)\s*(ml|mg)\b", r"\1.\2\3", s)
    s = re.sub(r"(\d+)\s*mls\b", r"\1ml", s)
    s = re.sub(r"(\d{2,4})\s*m\b", r"\1mg", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*[`'\u2019]?\s*s\b", r"\1s", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(mcg|mg|ml|gms|gm|kg|g|l|cc|iu|%)(?![a-z])", r"\1\2", s)
    s = re.sub(r"(\d+(?:\.\d+)?)(gms|gm)\b", r"\1g", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)
    s = re.sub(r"[^a-z0-9.% ]", " ", s)
    out = []
    for t in s.split():
        t = SYN.get(t, t)
        if t and t not in STOP:
            out.append(t)
    return out


def prep(name):
    units, words = {}, []
    for t in norm(name):
        m = UNIT_RE.match(t)
        if m:
            dim, mult = DIM[m.group(2)]
            units.setdefault(dim, set()).add(round(float(m.group(1)) * mult, 3))
        else:
            words.append(t)
    return units, words, " ".join(words)


@lru_cache(maxsize=None)
def tok_eq(a, b):
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.86


def score(F, P):
    fu, fw, fs = F
    pu, pw, ps = P
    if not fw or not pw:
        return 0.0
    bonus = 0.5
    for k in fu:
        if k in pu:
            if fu[k] & pu[k]:
                bonus = 1.0
            else:
                return 0.0          # same kind of unit, different amount: different strength or pack
    used, hit, exact = set(), 0, 0
    for a in pw:
        for i, b in enumerate(fw):
            if i not in used and tok_eq(a, b):
                hit += 1
                used.add(i)
                exact += (a == b)
                break
    cov = hit / len(pw)
    jac = hit / (len(pw) + len(fw) - hit)
    seq = SequenceMatcher(None, ps, fs).ratio()
    extra = sum(1 for k in fu if k not in pu)
    return max(0.0, 0.35 * cov + 0.2 * jac + 0.2 * seq + 0.15 * bonus + 0.10 * (exact / len(pw)) - 0.04 * extra)


class Command(BaseCommand):
    help = "Match photos in the Static folder to products. Dry run unless --apply is given."

    def add_arguments(self, p):
        p.add_argument("--apply", action="store_true", help="save the confident (OK) matches")
        p.add_argument("--include-review", action="store_true", help="also save REVIEW and TIE matches")
        p.add_argument("--overwrite", action="store_true", help="replace photos products already have")
        p.add_argument("--dept", choices=["chemist", "agrovet"])
        p.add_argument("--pin", action="append", default=[], help='force a match: "PRODUCT NAME=photo.jpg"')
        p.add_argument("--src", default=str(Path(settings.BASE_DIR).parent / "Static"))

    def handle(self, *a, **o):
        src = Path(o["src"])
        if not src.is_dir():
            raise CommandError("Photo folder not found: %s" % src)
        files = [(f, prep(f.name)) for f in sorted(src.iterdir()) if f.suffix.lower() in EXT]
        fmap = {f.name.lower(): f for f, _ in files}
        pins = {}
        for item in o["pin"]:
            if "=" not in item:
                raise CommandError('--pin needs the form "PRODUCT NAME=photo.jpg"')
            k, v = item.rsplit("=", 1)
            if v.strip().lower() not in fmap:
                raise CommandError("Pinned photo not found: %s" % v)
            pins[k.strip().lower()] = fmap[v.strip().lower()]

        prods = list(Product.objects.all().order_by("dept", "name", "pack"))
        if o["dept"]:
            prods = [p for p in prods if p.dept == o["dept"]]

        rows, used_files = [], set()
        for p in prods:
            key = p.name.strip().lower()
            if key in pins:
                best, second, st = (1.0, pins[key]), (0.0, None), "OK"
                used_files.add(pins[key].name)
                rows.append((p, best, second, st, bool(p.image)))
                continue
            P = prep("%s %s" % (p.name, p.pack or ""))
            sc = sorted(((score(F, P), f) for f, F in files), key=lambda x: -x[0])[:2]
            best = sc[0] if sc else (0.0, None)
            second = sc[1] if len(sc) > 1 else (0.0, None)
            if best[1] is not None and best[0] >= REVIEW_MIN:
                used_files.add(best[1].name)
            if best[0] >= OK_MIN and best[0] - second[0] >= TIE_GAP:
                st = "OK"
            elif best[0] >= OK_MIN:
                st = "TIE"
            elif best[0] >= REVIEW_MIN:
                st = "REVIEW"
            else:
                st = "NONE"
            rows.append((p, best, second, st, bool(p.image)))

        lines, counts = [], {}
        for st in ("OK", "TIE", "REVIEW", "NONE"):
            lines.append("")
            lines.append("===== %s =====" % st)
            for p, best, second, s, has in rows:
                if s != st or (has and not o["overwrite"]):
                    continue
                tag = " [pharmacist-guided, not public]" if getattr(p, "restricted", False) else ""
                label = "%s %s" % (p.name, ("[%s]" % p.pack) if p.pack else "")
                if st == "NONE":
                    lines.append("   -      %-9s %s%s" % (p.dept, label.strip(), tag))
                else:
                    extra = ""
                    if st == "TIE" and second[1] is not None:
                        extra = "   (also: %s %.2f)" % (second[1].name, second[0])
                    lines.append("%.2f  %-9s %s%s  <-  %s%s" % (best[0], p.dept, label.strip(), tag, best[1].name, extra))
                counts[(p.dept, st)] = counts.get((p.dept, st), 0) + 1

        unused = sorted(f.name for f, _ in files if f.name not in used_files)
        lines += ["", "===== PHOTOS NOT MATCHED TO ANY PRODUCT (%d) =====" % len(unused)] + ["   " + n for n in unused]
        Path("image_match_report.txt").write_text("\n".join(lines), encoding="utf-8")

        todo = [r for r in rows
                if (o["overwrite"] or not r[4])
                and (r[3] == "OK" or (o["include_review"] and r[3] in ("REVIEW", "TIE")))]
        if o["apply"]:
            dest = Path(settings.MEDIA_ROOT) / "products"
            dest.mkdir(parents=True, exist_ok=True)
            for p, best, second, st, has in todo:
                fpath = best[1]
                safe = re.sub(r"[^A-Za-z0-9._-]+", "_", fpath.name)
                shutil.copy(fpath, dest / safe)
                p.image.name = "products/" + safe
                p.save(update_fields=["image"])

        self.stdout.write("\n".join(lines))
        self.stdout.write("")
        done = {r[0].pk for r in todo} if o["apply"] else set()
        for dept in ("chemist", "agrovet"):
            total = sum(1 for r in rows if r[0].dept == dept)
            have = sum(1 for r in rows if r[0].dept == dept and (r[4] or r[0].pk in done))
            self.stdout.write("%-8s %3d products, %3d now have photos | still need a photo: %d" % (
                dept, total, have, total - have))
        if o["apply"]:
            self.stdout.write(self.style.SUCCESS("\nSAVED %d new photo(s). Full list: image_match_report.txt" % len(todo)))
        else:
            self.stdout.write(self.style.WARNING("\nDRY RUN - nothing saved. Full list: image_match_report.txt"))