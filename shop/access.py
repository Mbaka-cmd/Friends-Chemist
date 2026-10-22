"""Role gate: employees may only use the POS. Owners get the redesigned stock page."""
import re
from functools import lru_cache

from django.http import HttpResponseRedirect
from django.urls import get_resolver

STOCK_RE = re.compile(r"^/staff/(?P<dept>chemist|agrovet)/inventory/?$")
# Paths an employee may open. Extend this if the POS needs another endpoint.
ALLOWED = re.compile(
    r"(^|[/_.-])(pos|checkout|receipt|login|logout|password)([/_.-]|$)|search|autocomplete|lookup",
    re.I,
)

EMP_SCRIPT = r"""<script>(function(){
var ok=/(^|[\/_-])(pos|checkout|receipt|login|logout|password)([\/_-]|$)/i;
document.querySelectorAll('a[href]').forEach(function(a){
  var p;try{p=new URL(a.href,location.href).pathname}catch(e){return}
  if((p.indexOf('/staff/')===0||p.indexOf('/admin/')===0)&&!ok.test(p)){a.style.display='none'}
});
document.querySelectorAll('*').forEach(function(e){
  if(e.children.length===0){var t=(e.textContent||'').trim().toUpperCase();
    if(t==='OWNER'||t==='SITE'){e.style.display='none'}}
});})();</script>"""


def _walk(patterns, prefix=""):
    for p in patterns:
        route = prefix + str(p.pattern)
        if hasattr(p, "url_patterns"):
            yield from _walk(p.url_patterns, route)
        else:
            yield route


@lru_cache(maxsize=1)
def all_routes():
    out = []
    for r in _walk(get_resolver().url_patterns):
        r = r.replace("^", "").replace("$", "")
        if "<" in r or "(" in r or "?" in r:
            continue
        out.append("/" + r.lstrip("/"))
    return out


def find_route(kw, dept=None):
    hits = []
    for r in all_routes():
        if not r.startswith("/staff/"):
            continue
        if dept and ("/%s/" % dept) not in r:
            continue
        if kw in r.lower():
            hits.append(r)
    return min(hits, key=len) if hits else None


def pos_home():
    for r in all_routes():
        if r.startswith("/staff/") and re.search(r"(^|/)pos/?$", r):
            return r
    return find_route("pos")


def is_employee(user):
    return bool(
        user.is_authenticated
        and not user.is_superuser
        and user.groups.filter(name="Employee").exists()
    )


def _inject(resp):
    ct = resp.get("Content-Type", "")
    if getattr(resp, "streaming", False) or "text/html" not in ct:
        return resp
    html = resp.content.decode(resp.charset or "utf-8", "ignore")
    if "</body>" in html:
        html = html.replace("</body>", EMP_SCRIPT + "</body>", 1)
        resp.content = html.encode(resp.charset or "utf-8")
        if resp.has_header("Content-Length"):
            resp["Content-Length"] = str(len(resp.content))
    return resp


class StaffAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        user = getattr(request, "user", None)
        authed = user is not None and user.is_authenticated

        if authed and is_employee(user) and (path.startswith("/staff/") or path.startswith("/admin/")):
            if not ALLOWED.search(path):
                print("EMPLOYEE BLOCKED:", path)
                return HttpResponseRedirect(pos_home() or "/staff/login/")
            return _inject(self.get_response(request))

        m = STOCK_RE.match(path)
        if m and authed and not is_employee(user):
            is_edit = request.method == "POST" and request.headers.get("X-Stock-Edit") == "1"
            if is_edit or (request.method == "GET" and "classic" not in request.GET):
                from . import owner_stock
                return owner_stock.stock_page(request, m.group("dept"))

        return self.get_response(request)