from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from BS import views
from BS.views_errors import pagina_no_encontrada


urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.inicio, name="inicio"),
    path("terminos/", views.terminos, name="terminos"),
    path("privacidad/", views.privacidad, name="privacidad"),
    path("politica-uso/", views.politica_uso, name="politica_uso"),
    path(
        "politica-voluntariado/",
        views.politica_voluntariado,
        name="politica_voluntariado",
    ),
    path(
        "datos-personales/",
        views.datos_personales,
        name="datos_personales",
    ),
    path(
        "declaracion-accesibilidad/",
        views.declaracion_accesibilidad,
        name="declaracion_accesibilidad",
    ),

    path(
        "accounts/login/",
        RedirectView.as_view(pattern_name="acceso", permanent=False),
    ),
    path(
        "accounts/signup/",
        RedirectView.as_view(pattern_name="registro", permanent=False),
    ),
    path("accounts/", include("allauth.urls")),
    path("", include("BS.urls_cuentas")),
]

# Imágenes cargadas, únicamente durante el desarrollo.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Esta ruta general debe ser siempre la última.
urlpatterns += [
    re_path(r"^.*$", pagina_no_encontrada),
]