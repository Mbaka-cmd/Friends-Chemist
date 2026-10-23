from django import template
from django.core.paginator import Paginator
from shop.models import Product

register = template.Library()


def _group(items):
    groups = {}
    for p in items:
        key = (p.name or "").strip().lower()
        g = groups.setdefault(key, {"rep": p, "packs": set(), "prices": []})
        if not g["rep"].image and p.image:
            g["rep"] = p
        g["packs"].add((p.pack or "").strip().lower())
        if p.sell_price:
            g["prices"].append(p.sell_price)
    out = []
    for g in groups.values():
        rep = g["rep"]
        rep.sizes = len(g["packs"])
        rep.from_price = min(g["prices"]) if g["prices"] else None
        out.append(rep)
    return out


@register.simple_tag(takes_context=True)
def grouped_page(context, page_obj):
    request = context["request"]
    per_page = page_obj.paginator.per_page
    items = _group(page_obj.paginator.object_list)
    return Paginator(items, per_page).get_page(request.GET.get("page"))


@register.simple_tag
def product_sizes(p):
    seen, out = set(), []
    qs = (Product.objects
          .filter(dept=p.dept, name__iexact=p.name, is_public=True, active=True)
          .order_by("sell_price", "pack"))
    for s in qs:
        k = (s.pack or "").strip().lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


@register.simple_tag
def hero_ring(dept="agrovet", n=8):
    seen, out = set(), []
    qs = (Product.objects
          .filter(dept=dept, is_public=True, active=True)
          .exclude(image="")
          .order_by("?"))
    for p in qs:
        if p.image.name in seen:
            continue
        seen.add(p.image.name)
        out.append(p)
        if len(out) >= n:
            break
    return out


@register.simple_tag
def cat_info(dept, cat):
    qs = Product.objects.filter(dept=dept, category=cat, is_public=True, active=True, restricted=False)
    photo = qs.exclude(image="").order_by("?").first()
    return {"count": qs.count(), "photo": photo}

# ---- v3 overrides: grouping, curated homepage, safer photos ----
import re
import random
from urllib.parse import quote

HOME_PINS = {
    # Edit this list to change which medicines lead the homepage (exact product names, in order).
    "chemist": [
        "PANADOL ADVANCE 100s", "PANADOL EXTRA TABS 100s",
        "PCM CALPOL SUSP 100ML", "PCM CALPOL SUSP 60ML", "PCM TRUMOL 60ML",
        "SCOTTS ORANGE 100ML", "SCOTTS ORIGINAL 100ML", "SEVEN SEA 100ML",
        "CYPRO B PLUS SYRUP 200ML",
        "TRICOHIST 100MLS", "TRICOHIST EXP 60ML",
    ],
    "agrovet": [],
}
AVOID_HOME = ("kiss",)      # still sold in the shop, kept off homepage photos and featured
_GENERIC_FIRST = {"pcm", "multivitamin", "vitamin", "vitamins"}


def _fam_words(name):
    words = re.findall(r"[A-Za-z]+", name or "")
    if not words:
        return [(name or "").strip()]
    n = 2 if words[0].lower() in _GENERIC_FIRST and len(words) > 1 else 1
    return words[:n]


def _fam_key(p):
    if p.dept == "chemist":
        return "c:" + " ".join(w.lower() for w in _fam_words(p.name))
    return "n:" + (p.name or "").strip().lower()


def _fam_title(p):
    return " ".join(w if (len(w) <= 3 and w.isupper()) else w.capitalize() for w in _fam_words(p.name))


def _variant_label(name, n):
    s = (name or "").strip()
    for _ in range(n):
        s = re.sub(r"^[^A-Za-z]*[A-Za-z]+", "", s, count=1)
    return s.strip(" -()/")


def _avoided(name):
    nm = (name or "").strip().lower()
    return any(nm.startswith(a) for a in AVOID_HOME)


def _group(items):
    groups = {}
    for p in items:
        g = groups.setdefault(_fam_key(p), {"rep": p, "m": [], "prices": []})
        g["m"].append(p)
        if not g["rep"].image and p.image:
            g["rep"] = p
        if p.sell_price:
            g["prices"].append(p.sell_price)
    out = []
    for g in groups.values():
        rep, m = g["rep"], g["m"]
        if rep.dept == "chemist":
            rep.sizes = len(m)
            rep.card_name = _fam_title(rep) if len(m) > 1 else ""
        else:
            rep.sizes = len({(x.pack or "").strip().lower() for x in m})
            rep.card_name = ""
        rep.from_price = min(g["prices"]) if g["prices"] else None
        rep.family_members = m
        out.append(rep)
    return out


def _pinned(groups, dept):
    out, seen = [], set()
    for name in HOME_PINS.get(dept, []):
        nm = name.strip().lower()
        for g in groups:
            hit = next((x for x in g.family_members if (x.name or "").strip().lower() == nm), None)
            if hit is None:
                continue
            if _fam_key(hit) not in seen:
                if hit is not g:
                    hit.sizes, hit.from_price = g.sizes, g.from_price
                    hit.card_name, hit.family_members = g.card_name, g.family_members
                seen.add(_fam_key(hit))
                out.append(hit)
            break
    return out, seen


@register.simple_tag
def featured(dept, n=12):
    qs = Product.objects.filter(dept=dept, is_public=True, active=True, restricted=False).order_by("name", "pack")
    groups = _group(qs)
    out, seen = _pinned(groups, dept)
    out = out[:n]
    buckets = {}
    for g in groups:
        if g.image and not _avoided(g.name) and _fam_key(g) not in seen:
            buckets.setdefault(g.category, []).append(g)
    while len(out) < n and any(buckets.values()):
        for k in sorted(buckets):
            if buckets[k] and len(out) < n:
                x = buckets[k].pop(0)
                seen.add(_fam_key(x))
                out.append(x)
    for g in groups:
        if len(out) >= n:
            break
        if _fam_key(g) not in seen and not _avoided(g.name):
            seen.add(_fam_key(g))
            out.append(g)
    return out


@register.simple_tag
def hero_ring(dept="agrovet", n=8):
    qs = (Product.objects.filter(dept=dept, is_public=True, active=True, restricted=False)
          .exclude(image="").order_by("name", "pack"))
    groups = _group(qs)
    out, seen = _pinned(groups, dept)
    rest = [g for g in groups if _fam_key(g) not in seen and not _avoided(g.name)]
    random.shuffle(rest)
    result, imgs = [], set()
    for g in out + rest:
        if g.image and g.image.name not in imgs:
            imgs.add(g.image.name)
            result.append(g)
        if len(result) >= n:
            break
    return result


@register.simple_tag
def cat_card(dept, cat):
    qs = Product.objects.filter(dept=dept, category=cat, is_public=True, active=True, restricted=False)
    fams = {_fam_key(p) for p in qs}
    slug = re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")
    rel = "shop/img/cat-%s.jpg" % slug
    photo, cover = "", False
    if finders.find(rel):
        photo, cover = _static(rel), True
    else:
        with_img = [p for p in qs.exclude(image="").order_by("name") if not _avoided(p.name)]
        pins = [x.strip().lower() for x in HOME_PINS.get(dept, [])]
        pick = next((p for nm in pins for p in with_img if (p.name or "").strip().lower() == nm), None)
        if pick is None and with_img:
            pick = with_img[0]
        if pick is not None:
            photo = pick.image.url
    return {"count": len(fams), "photo": photo, "cover": cover, "slug": slug,
            "desc": CAT_DESC.get(cat, "Browse our range of %s." % cat.lower())}


@register.simple_tag
def product_sizes(p):
    qs = Product.objects.filter(dept=p.dept, is_public=True, active=True)
    if p.dept == "chemist":
        key = _fam_key(p)
        fam = [s for s in qs.filter(restricted=False).order_by("name") if _fam_key(s) == key]
        n = len(_fam_words(p.name))
        for i, s in enumerate(fam, 1):
            s.vlabel = _variant_label(s.name, n) or s.pack or ("Option %d" % i)
        return fam
    seen, out = set(), []
    for s in qs.filter(name__iexact=p.name).order_by("sell_price", "pack"):
        k = (s.pack or "").strip().lower()
        if k not in seen:
            seen.add(k)
            s.vlabel = s.pack or ""
            out.append(s)
    return out


@register.simple_tag
def wa_link(p=None, text=""):
    if p is not None:
        cn = getattr(p, "card_name", "") or ""
        name = cn or p.name
        pack = " (%s)" % p.pack if (p.pack and not cn) else ""
        text = "Hello Friends %s, I would like to enquire about %s%s." % ((p.dept or "").title(), name, pack)
    return "https://wa.me/%s?text=%s" % (globals().get("WA_NUMBER", "254716217239"), quote(text))