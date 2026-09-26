from django.shortcuts import render


def inicio(request):
    return render(request, "publica/index.html")


def acceso(request):
    return render(request, "cuentas/login.html")


def registro(request):
    return render(request, "cuentas/registro.html")


def recuperar_clave(request):
    return render(request, "cuentas/recuperar_clave.html")

def terminos(request):
    return render(request, "publica/legales/terminos.html")


def privacidad(request):
    return render(request, "publica/legales/privacidad.html")


def politica_uso(request):
    return render(request, "publica/legales/politica_uso.html")


def politica_voluntariado(request):
    return render(request, "publica/legales/politica_voluntariado.html")


def datos_personales(request):
    return render(request, "publica/legales/datos_personales.html")