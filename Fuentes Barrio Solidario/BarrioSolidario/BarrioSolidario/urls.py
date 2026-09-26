from django.contrib import admin
from django.urls import path
from BS import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.inicio, name="inicio"),
    path("acceso/", views.acceso, name="acceso"),
    path("registro/", views.registro, name="registro"),
    path(
        "recuperar-clave/",
        views.recuperar_clave,
        name="recuperar_clave",
    ),
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
]