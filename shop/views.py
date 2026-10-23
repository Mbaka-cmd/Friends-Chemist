"""Editable entry point for the shop views.

views_legacy.pyc is an unchanged copy of the original compiled views module.
Everything not overridden below is the original code.
"""
import logging
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from . import views_legacy as _L

_log = logging.getLogger(__name__)

# Re-export everything (shop.urls and other modules import names from shop.views).
globals().update({k: v for k, v in vars(_L).items() if not k.startswith("__")})

ALL_DEPTS = ("chemist", "agrovet")
RECEIVE_KINDS = ("receipt", "opening")


def allowed(user):
    """Departments a user may work in. Reads the explicit access flags only."""
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return []
    if user.is_superuser:
        return list(ALL_DEPTS)
    pr = getattr(user, "profile", None)
    if pr is None:
        return []
    out = []
    if pr.access_chemist:
        out.append("chemist")
    if pr.access_agrovet:
        out.append("agrovet")
    return out


# The compiled views call allowed() through their own module globals, so patch it there as well.
_L.allowed = allowed

_legacy_stock = _L.stock
_legacy_ledger = _L.ledger
_legacy_inventory = _L.inventory


@wraps(_legacy_stock)
def stock(request, dept, *a, **k):
    u = request.user
    if u.is_authenticated and not u.is_superuser and dept in allowed(u):
        pr = getattr(u, "profile", None)
        can_receive = bool(pr and pr.can_receive_stock)
        can_adjust = bool(pr and pr.can_adjust_stock)
        if not (can_receive or can_adjust):
            return HttpResponseForbidden("You do not have permission to receive or adjust stock.")
        if request.method == "POST":
            kind = (request.POST.get("kind") or "").strip().lower()
            if kind in RECEIVE_KINDS:
                if not can_receive:
                    return HttpResponseForbidden("You may not record supplier receipts.")
            else:
                if not can_adjust:
                    return HttpResponseForbidden("You may not record stock adjustments.")
                try:
                    qty = int((request.POST.get("qty") or "0").strip())
                except ValueError:
                    qty = 0
                if abs(qty) > pr.adjust_limit:
                    return HttpResponseForbidden("Adjustment is above your limit of %d units." % pr.adjust_limit)
                post = request.POST.copy()
                for f in ("cost", "supplier"):
                    post.pop(f, None)
                request.POST = post
    return _legacy_stock(request, dept, *a, **k)


@wraps(_legacy_ledger)
def ledger(request, dept, kind, *a, **k):
    u = request.user
    if u.is_authenticated and not u.is_superuser and kind == "sales" and dept in allowed(u):
        return redirect("/staff/%s/sales/" % dept)
    return _legacy_ledger(request, dept, kind, *a, **k)


@wraps(_legacy_inventory)
def inventory(request, dept, *a, **k):
    u = request.user
    if u.is_authenticated and u.is_active and u.is_superuser and dept in ALL_DEPTS:
        is_edit = request.method == "POST" and request.headers.get("X-Stock-Edit") == "1"
        if is_edit or (request.method == "GET" and "classic" not in request.GET):
            try:
                from . import owner_stock
                resp = owner_stock.stock_page(request, dept)
                resp["X-No-Zoom"] = "1"
                return resp
            except Exception:
                _log.exception("owner stock page failed; falling back to the classic page")
    return _legacy_inventory(request, dept, *a, **k)
