import csv
import json
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.views.decorators.csrf import csrf_protect

from .access import find_route, is_employee
from .models import Product

DEPTS = {"chemist": "Friends Chemist", "agrovet": "Friends Agrovet"}


def _safe(v):
    # step4: neutralise spreadsheet formulas in CSV exports
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _num(v):
    if callable(v):
        v = v()
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _rows(dept):
    out = []
    for p in Product.objects.filter(dept=dept).order_by("name", "pack"):
        qty = _num(getattr(p, "sellable", 0))
        reorder = p.reorder_level or 0
        st = "out" if qty <= 0 else ("low" if qty <= reorder else "ok")
        out.append({
            "p": p,
            "qty": int(qty) if qty == int(qty) else qty,
            "st": st,
            "hidden": not p.is_public,
            "noprice": not p.sell_price,
        })
    return out


def _nav(dept):
    def item(label, kw, d=None, href=None):
        h = href or find_route(kw, d)
        return (label, h, kw == "inventory") if h else None

    shop = [item("Stock management", "inventory", dept),
            item("Receive / adjust", "receive", dept),
            item("Batches & expiry", "batch", dept),
            item("Stock movements", "movement", dept),
            item("Sales", "sales", dept),
            item("POS", "pos", dept),
            item("Reports", "report", dept),
            item("Enquiries", "enquir", dept)]
    owner = [item("Profit & loss", "finance"),
             item("Expenses", "expens"),
             item("Products, users, settings", "admin", href="/admin/")]
    site = [item("Chemist storefront", "x", href="/chemist/"),
            item("Agrovet storefront", "x", href="/agrovet/")]
    groups = [
        {"title": "", "items": [("Dashboard", "/staff/", False)]},
        {"title": DEPTS[dept].replace("Friends ", "").upper(), "items": [i for i in shop if i]},
        {"title": "OWNER", "items": [i for i in owner if i]},
        {"title": "SITE", "items": [i for i in site if i]},
    ]
    return groups


def _csv(dept):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="%s-stock.csv"' % dept
    w = csv.writer(resp)
    w.writerow(["SKU", "Name", "Pack", "Category", "Buy price", "Sell price",
                "In stock", "Reorder at", "Status", "On website"])
    for r in _rows(dept):
        p = r["p"]
        w.writerow([_safe(x) for x in (p.sku, p.name, p.pack, p.category, p.buy_price or "", p.sell_price or "",
                    r["qty"], p.reorder_level or 0, r["st"], "yes" if p.is_public else "no")])
    return resp


def _update(request, dept):
    if not request.user.is_authenticated or not request.user.is_superuser:  # step4: owner only
        return JsonResponse({"ok": False, "error": "Not allowed"}, status=403)
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Bad request"}, status=400)
    p = Product.objects.filter(pk=data.get("id"), dept=dept).first()
    field, value = data.get("field"), data.get("value")
    if not p or field not in ("sell_price", "buy_price", "reorder_level", "is_public", "active"):
        return JsonResponse({"ok": False, "error": "Unknown product or field"}, status=400)
    try:
        if field in ("sell_price", "buy_price"):
            if value in ("", None):
                value = None
            else:
                value = Decimal(str(value)).quantize(Decimal("0.01"))
                if value < 0:
                    raise ValueError
        elif field == "reorder_level":
            value = int(value)
            if value < 0:
                raise ValueError
        else:
            value = bool(value)
        old_value = getattr(p, field)
        setattr(p, field, value)
        p.save(update_fields=[field])
        from .services import audit
        audit(request.user, "product_edit", "%s %s %s -> %s" % (p.sku, field, old_value, value))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Enter a valid number"}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)[:120]}, status=400)
    return JsonResponse({"ok": True})


@csrf_protect
def stock_page(request, dept):
    if not (request.user.is_authenticated and request.user.is_superuser):  # step4: owner only
        return HttpResponseForbidden("Owner only.")
    if dept not in DEPTS:
        return HttpResponseForbidden("Unknown department.")
    if request.method == "POST":
        return _update(request, dept)
    if request.GET.get("export") == "csv":
        return _csv(dept)

    rows = _rows(dept)
    counts = {
        "total": len(rows),
        "ok": sum(1 for r in rows if r["st"] == "ok"),
        "low": sum(1 for r in rows if r["st"] == "low"),
        "out": sum(1 for r in rows if r["st"] == "out"),
        "noprice": sum(1 for r in rows if r["noprice"]),
        "hidden": sum(1 for r in rows if r["hidden"]),
    }
    cats = sorted({r["p"].category for r in rows if r["p"].category})
    try:
        add_url = reverse("admin:shop_product_add")
    except NoReverseMatch:
        add_url = "/admin/shop/product/add/"
    change_base = add_url[:-4] if add_url.endswith("add/") else "/admin/shop/product/"
    ctx = {
        "dept": dept,
        "dept_name": DEPTS[dept],
        "rows": rows,
        "counts": counts,
        "cats": cats,
        "nav": _nav(dept),
        "csrf": get_token(request),
        "username": request.user.get_username(),
        "add_url": add_url,
        "change_base": change_base,
        "receive_url": find_route("receive", dept),
        "classic_url": request.path + "?classic=1",
        "csv_url": request.path + "?export=csv",
        "logout_url": find_route("logout") or "/staff/logout/",
        "all_out": counts["total"] > 0 and counts["ok"] + counts["low"] == 0,
    }
    return HttpResponse(render_to_string("shop/owner_stock.html", ctx, request=request))