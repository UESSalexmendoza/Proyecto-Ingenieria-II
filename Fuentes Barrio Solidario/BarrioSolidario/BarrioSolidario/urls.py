from django.contrib import admin
from django.urls import path, include
from BS import views

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
    path("", include("BS.urls_cuentas")),    
]