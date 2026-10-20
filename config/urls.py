from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from shop import site_extras as x

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/chemist/')),
    path('contact/', x.contact, name='contact'),
    re_path(r'^staff/(?P<dept>[^/]+)/inventory/$', x.zoomed),
    path('', include('shop.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)