"""Agrega el backend de roles sin reemplazar la configuración existente.

Ejecutar desde la carpeta que contiene manage.py:
    python configurar_backend_roles.py
"""
from pathlib import Path
import ast

archivo = Path(__file__).resolve().parent / "BarrioSolidario" / "settings.py"
if not archivo.is_file():
    raise SystemExit("No se encontró BarrioSolidario/settings.py junto a este script.")
contenido = archivo.read_text(encoding="utf-8")
modulo = ast.parse(contenido)
objetivo = next((n for n in modulo.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "AUTHENTICATION_BACKENDS" for t in n.targets)), None)
if objetivo is None or not isinstance(objetivo.value, (ast.List, ast.Tuple)):
    raise SystemExit("AUTHENTICATION_BACKENDS no es una lista o tupla literal; agrégalo manualmente.")
valores = [n.value for n in objetivo.value.elts if isinstance(n, ast.Constant) and isinstance(n.value, str)]
if len(valores) != len(objetivo.value.elts):
    raise SystemExit("La lista tiene expresiones dinámicas; agrégalo manualmente para preservarlas.")
backend = "BS.backends.BarrioRolBackend"
if backend in valores:
    print("El backend de roles ya está configurado.")
else:
    if "django.contrib.auth.backends.ModelBackend" not in valores:
        raise SystemExit("No se encontró ModelBackend; revisa los backends existentes antes de continuar.")
    lineas = contenido.splitlines(keepends=True)
    inicio = objetivo.value.lineno - 1
    fin = objetivo.value.end_lineno
    bloque = "".join(lineas[inicio:fin])
    referencia = next((linea for linea in bloque.splitlines(keepends=True) if '"django.contrib.auth.backends.ModelBackend"' in linea or "'django.contrib.auth.backends.ModelBackend'" in linea), None)
    if referencia is None:
        raise SystemExit("La entrada ModelBackend usa una sintaxis no reconocida; agrégalo manualmente.")
    indentacion = referencia[:len(referencia)-len(referencia.lstrip())]
    insercion = f'{indentacion}"{backend}",\n'
    indice = lineas.index(referencia, inicio, fin)
    lineas.insert(indice + 1, insercion)
    resultado = "".join(lineas)
    ast.parse(resultado)
    archivo.write_text(resultado, encoding="utf-8")
    print("Backend de roles agregado a AUTHENTICATION_BACKENDS.")
