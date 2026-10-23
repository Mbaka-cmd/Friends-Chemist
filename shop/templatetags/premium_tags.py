import re
from types import SimpleNamespace
from urllib.parse import quote
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static as _static
from shop.models import Product

register = template.Library()
WA_NUMBER = '254716217239'   # WhatsApp number, international format, no +. Change here if different.
PHONE_DISPLAY, PHONE_TEL = '0716 217239', '0716217239'
HIDE = {'To be categorised'}
CAT_DESC = {
    'Animal health': 'Animal-health products. Ask us for guidance.',
    'Crop protection': 'Crop-care products. Ask us before you buy.',
    'Crop nutrition': 'Boosters and fertilisers for stronger crops.',
    'Equipment & supplies': 'Practical supplies for the farm.',
    'Milk replacers': 'Milk replacers for young stock.',
    'Minerals & supplements': 'Mineral licks, blocks and supplements.',
    'Pain Relief': 'Everyday pain relief.', 'Cough & Cold': 'Cough and cold remedies.',
    'Vitamins & Supplements': 'Vitamins and supplements.', 'Stomach & Digestive': 'Stomach and digestive care.',
    'Skin Care & Creams': 'Creams, ointments and skin care.', 'Family Planning & Wellness': 'Family planning and wellness.',
}

def _pub(dept):
    return Product.objects.filter(dept=dept, is_public=True, active=True)

@register.simple_tag
def biz():
    return {'place': 'Kibugua', 'phone': PHONE_DISPLAY, 'tel': PHONE_TEL, 'wa': 'https://wa.me/' + WA_NUMBER}

@register.simple_tag
def wa_link(p=None, text=''):
    if p is not None:
        pack = ' (%s)' % p.pack if p.pack else ''
        text = 'Hello Friends %s, I would like to enquire about %s%s.' % ('Agrovet' if p.dept == 'agrovet' else 'Chemist', p.name, pack)
    return 'https://wa.me/%s?text=%s' % (WA_NUMBER, quote(text))

@register.simple_tag
def shop_cats(dept):
    qs = _pub(dept).exclude(category='').values_list('category', flat=True).distinct().order_by('category')
    return [c for c in qs if c not in HIDE]

@register.simple_tag
def cat_card(dept, cat):
    qs = _pub(dept).filter(category=cat)
    names = {(n or '').strip().lower() for n in qs.values_list('name', flat=True)}
    rel = 'shop/img/cat-%s.jpg' % re.sub(r'[^a-z0-9]+', '-', cat.lower()).strip('-')
    photo, cover = '', False
    if finders.find(rel): photo, cover = _static(rel), True
    else:
        p = qs.exclude(image='').order_by('restricted', 'name').first()
        if p: photo = p.image.url
    return {'count': len(names), 'photo': photo, 'cover': cover, 'desc': CAT_DESC.get(cat, 'Browse %s.' % cat.lower())}

@register.simple_tag
def group_products(items):
    groups, order = {}, []
    for p in (items or []):
        key = ((p.name or '').strip().lower(), p.category)
        g = groups.get(key)
        if g is None:
            g = groups[key] = SimpleNamespace(first=p, sizes=0, prices=[], img=None); order.append(key)
        g.sizes += 1
        if p.sell_price: g.prices.append(p.sell_price)
        if p.image and g.img is None: g.img = p
    out = []
    for k in order:
        g = groups[k]; rep = g.img or g.first
        rep.sizes, rep.from_price = g.sizes, (min(g.prices) if g.prices else None)
        out.append(rep)
    return out

def _spread(groups, n):
    buckets = {}
    for g in groups: buckets.setdefault(g.category, []).append(g)
    out = []
    while len(out) < n and any(buckets.values()):
        for k in sorted(buckets):
            if buckets[k] and len(out) < n: out.append(buckets[k].pop(0))
    return out

@register.simple_tag
def featured(dept, n=12):
    groups = group_products(_pub(dept).exclude(restricted=True).exclude(category__in=HIDE).order_by('name', 'pack'))
    with_img = [g for g in groups if g.image]
    out = _spread(with_img, n)
    return out + [g for g in groups if not g.image][: max(0, n - len(out))]

@register.simple_tag
def hero_stage(dept, n=4):
    groups = group_products(_pub(dept).exclude(restricted=True).exclude(image='').order_by('name'))
    return _spread(groups, n)

@register.simple_tag
def siblings(p):
    return list(_pub(p.dept).filter(name__iexact=p.name).order_by('sell_price', 'pack'))

@register.simple_tag
def related(p, n=4):
    qs = _pub(p.dept).filter(category=p.category).exclude(name__iexact=p.name).order_by('restricted', 'name')
    groups = group_products(qs)
    return ([g for g in groups if g.image] + [g for g in groups if not g.image])[:n]