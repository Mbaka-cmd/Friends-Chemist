from django.shortcuts import render
from django.urls import resolve
from urllib.parse import quote

PHONE = '0716 217239'
WHATSAPP = '254716217239'
ZOOM = '<style>html{zoom:.67}</style>'


def contact(request):
    msg = 'Hello, I would like to ask about your products.'
    return render(request, 'shop/contact.html', {
        'phone': PHONE,
        'wa_num': WHATSAPP,
        'show_map': True,
        'wa': 'https://wa.me/%s?text=%s' % (WHATSAPP, quote(msg)),
    })


def zoomed(request, *args, **kwargs):
    m = resolve(request.path_info, urlconf='shop.urls')
    resp = m.func(request, *m.args, **m.kwargs)
    if hasattr(resp, 'render') and not getattr(resp, 'is_rendered', True):
        resp.render()
    if resp.status_code == 200 and 'text/html' in resp.get('Content-Type', '') and hasattr(resp, 'content'):
        html = resp.content.decode('utf-8')
        if '</head>' in html:
            html = html.replace('</head>', ZOOM + '</head>', 1)
        else:
            html = ZOOM + html
        resp.content = html.encode('utf-8')
    return resp