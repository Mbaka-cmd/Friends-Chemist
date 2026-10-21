from django import template
register = template.Library()
M = [('seed', '\U0001F331'), ('fertili', '\U0001F9EA'), ('nutrition', '\U0001F9EA'), ('protect', '\U0001F6E1'), ('feed', '\U0001F33E'),
     ('vet', '\U0001F404'), ('equip', '\U0001F69C'), ('pain', '\U0001F48A'), ('cough', '\U0001F927'), ('vitamin', '\U0001F34A'),
     ('skin', '\U0001F9F4'), ('stomach', '\U0001FAE7'), ('antibio', '\U0001F9A0'), ('heart', '\u2764'), ('diabet', '\U0001FA78'),
     ('family', '\U0001F496'), ('first', '\U0001FA79')]
@register.filter
def icon(v):
    v = (v or '').lower()
    return next((e for k, e in M if k in v), '\U0001F4E6')
@register.filter
def shape(p):
    n = (p.name + ' ' + p.category + ' ' + p.pack).upper()
    if p.dept == 'agrovet':
        if any(k in n for k in ('FEED', 'MASH', 'MEAL', 'PELLET', 'FERTILIZER', 'SALT', ' KG')): return 'bag'
        if any(k in n for k in (' 1 L', ' ML', 'VETERINARY')): return 'bottle'
        return 'packet'
    if any(k in n for k in ('CREAM', 'OINT', 'BALM', 'GEL', 'DEEP HEAT')): return 'tube'
    if any(k in n for k in ('SYP', 'SYRUP', 'SUSP', 'ML', 'WATER', 'SALT')): return 'bottle'
    if any(k in n for k in ('KISS', 'KIT')): return 'box'
    return 'pack'
# ---- v7 ----
from django.utils.html import escape
from django.utils.safestring import mark_safe

@register.filter
def rich(text):
    out, items = [], []
    def flush():
        if items: out.append('<ul>' + ''.join('<li>%s</li>' % escape(i) for i in items) + '</ul>'); items.clear()
    for line in (text or '').splitlines():
        s = line.strip()
        if s.startswith(('* ', '- ')): items.append(s[2:]); continue
        flush()
        if s.startswith('## '): out.append('<h4>%s</h4>' % escape(s[3:]))
        elif s: out.append('<p>%s</p>' % escape(s))
    flush()
    return mark_safe(''.join(out))

@register.filter
def kv(text):
    return [tuple(x.strip() for x in l.split(':', 1)) for l in (text or '').splitlines() if ':' in l]
