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