from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render

DOT = "\u00b7"
PHONE = "0716 217239"

COPY = {
    "chemist": {
        "brand": "Friends Chemist",
        "tag": "Health %s Wellness %s Community" % (DOT, DOT),
        "ann1": "Your local pharmacy", "ann2": "Everyday health products",
        "eyebrow": "QUALITY CARE / TRUSTED BRANDS",
        "h1a": "Your health,", "h1b": "made simpler.",
        "lead": "Shop everyday health essentials and get helpful guidance from our pharmacist in Kibugua.",
        "talk": "Talk to a pharmacist",
        "feat_h": "Everyday health essentials",
        "as_label": "Friends Pharmacy Desk",
        "as_text": "Search our catalogue, browse categories, or message our pharmacist on WhatsApp for guidance.",
        "as_cta": "Message the pharmacist",
        "as_talk": "Talk to a pharmacist", "as_talk_sub": "Get expert advice",
        "rx_h": "Need prescription support?",
        "rx_t": "Speak directly with our pharmacist about prescription medicines.",
        "rx_b": "Speak to our pharmacist",
        "wa_msg": "Hello Friends Chemist, I would like to speak to the pharmacist.",
        "meta": "Friends Chemist in Kibugua: everyday health products and pharmacist guidance.",
    },
    "agrovet": {
        "brand": "Friends Agrovet",
        "tag": "Animal health %s Farm supplies" % DOT,
        "ann1": "Your local agrovet", "ann2": "Animal health and farm supplies",
        "eyebrow": "ANIMAL HEALTH / FARM SUPPLIES",
        "h1a": "Farm care,", "h1b": "made simpler.",
        "lead": "Animal health products, feeds and farm supplies from our Kibugua shop.",
        "talk": "Talk to our team",
        "feat_h": "Farm essentials",
        "as_label": "Friends Agrovet Desk",
        "as_text": "Search our catalogue, browse categories, or message our team on WhatsApp for help choosing.",
        "as_cta": "Message our team",
        "as_talk": "Talk to our team", "as_talk_sub": "Ask before you buy",
        "rx_h": "Need help choosing a product?",
        "rx_t": "Tell us what you need and our team will help you find it.",
        "rx_b": "Message our team",
        "wa_msg": "Hello Friends Agrovet, I would like some help choosing a product.",
        "meta": "Friends Agrovet in Kibugua: animal health products, feeds and farm supplies.",
    },
}
OTHER = {"chemist": ("agrovet", "Agrovet"), "agrovet": ("chemist", "Chemist")}


def _stock(p):
    """'in' only when the model clearly reports positive stock; otherwise nothing is claimed."""
    for a in ("in_stock", "is_in_stock", "stock_qty", "stock", "qty", "quantity", "on_hand"):
        try:
            v = getattr(p, a, None)
            if callable(v):
                v = v()
        except Exception:
            continue
        if isinstance(v, bool):
            return "in" if v else ""
        if isinstance(v, (int, float, Decimal)):
            return "in" if v > 0 else ""
    return ""


def build(dept):
    from .models import Product
    from .templatetags import pack_sizes as t

    c = COPY[dept]
    num = getattr(t, "WA_NUMBER", "254716217239")

    def wa(text):
        return "https://wa.me/%s?text=%s" % (num, quote(text))

    base = Product.objects.filter(dept=dept, is_public=True, active=True, restricted=False)

    def link(p):
        return "/%s/%s/" % (dept, p.sku)

    ring = [p for p in t.hero_ring(dept, 12) if p.image]
    chunks = [ring[i:i + 4] for i in range(0, len(ring), 4)]
    chunks = [ch for ch in chunks if len(ch) >= 3] or chunks[:1]
    slides = [[{"name": p.public_name, "img": p.image.url, "href": link(p)} for p in ch] for ch in chunks]

    cats = []
    for n in [x for x in base.values_list("category", flat=True).distinct() if x]:
        try:
            cd = t.cat_card(dept, n)
        except Exception:
            cd = {"count": base.filter(category=n).count(), "photo": ""}
        cats.append({"name": n, "count": cd["count"], "photo": cd["photo"],
                     "href": "/%s/?cat=%s" % (dept, quote(n))})
    order = list(getattr(t, "COVER_PICKS", {}).keys())
    cats.sort(key=lambda x: (order.index(x["name"]) if x["name"] in order else 99, -x["count"], x["name"]))

    feats = []
    for p in t.featured(dept, 8):
        n = getattr(p, "sizes", 1) or 1
        if n > 1:
            pack = "%d %s" % (n, "options" if dept == "chemist" else "sizes")
        else:
            pack = p.pack or ""
        feats.append({
            "name": getattr(p, "card_name", "") or p.public_name,
            "cat": p.category or "", "pack": pack,
            "price": getattr(p, "from_price", None) or p.sell_price, "from": n > 1,
            "img": p.image.url if p.image else "", "href": link(p),
            "wa": t.wa_link(p), "stock": _stock(p),
        })

    od, ol = OTHER[dept]
    return {
        "dept": dept, "c": c, "slides": slides, "cats": cats, "feats": feats,
        "other": {"href": "/%s/" % od, "label": ol}, "phone": PHONE, "tel": "+" + num,
        "wa_talk": wa(c["wa_msg"]),
    }


class HomeV5Middleware:
    """Serves the redesigned homepage for /chemist/ and /agrovet/, and opens Agrovet first.
    Set HOME_V5 = False in settings.py to switch this off."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET" and getattr(settings, "HOME_V5", True):
            path = request.path.strip("/")
            if request.path == "/":
                return HttpResponseRedirect("/agrovet/")
            if path in COPY and not any(k for k in request.GET if not k.startswith("utm_")):
                return render(request, "shop/home_v5.html", build(path))
        return self.get_response(request)