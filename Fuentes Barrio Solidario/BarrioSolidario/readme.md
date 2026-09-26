# Barrio Solidario — instalación desde Git

Esta guía permite descargar y ejecutar el proyecto Django en un equipo nuevo. Coloca este archivo en la **raíz del repositorio**, junto a `manage.py`.

## Requisitos

- Git.
- Python 3 y `pip` (usa la versión de Python indicada por el proyecto, si está especificada).
- Acceso al repositorio de Barrio Solidario.

## 1. Clonar el proyecto

Abre PowerShell y clona el repositorio:

```powershell
git clone https://github.com/UESSalexmendoza/Proyecto-Ingenieria-II.git
cd Proyecto-Ingenieria-II
```

Comprueba que en esa carpeta exista `manage.py`. Si el repositorio contiene una carpeta adicional con el proyecto, entra en ella antes de continuar.

## 2. Crear y activar un entorno virtual

El entorno `.venv` **no se incluye en Git** por su tamaño y porque depende del equipo donde se crea. Cada integrante debe generarlo localmente después de clonar el proyecto; las dependencias se recuperan desde `requirements.txt`.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell impide activar el entorno, usa una ventana de CMD y ejecuta `.venv\Scripts\activate.bat`. En macOS o Linux, ejecuta `python3 -m venv .venv` y `source .venv/bin/activate`.

## 3. Instalar las dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

El repositorio debe incluir `requirements.txt`. Si aún no existe, créalo desde el entorno donde el proyecto ya funciona con `python -m pip freeze > requirements.txt` y súbelo a Git. Si de momento el proyecto solo usa Django, se puede empezar instalando `python -m pip install django` y después generar el archivo; añade las demás dependencias reales antes de compartirlo.

## 4. Configurar el entorno

Si el repositorio incluye `.env.example`, cópialo y completa los valores requeridos:

```powershell
Copy-Item .env.example .env
```

Configura la base de datos y las variables que efectivamente lea `BarrioSolidario/settings.py`. No subas a Git `.env`, claves secretas ni contraseñas. Si se usa la configuración predeterminada de SQLite para desarrollo, no hace falta crear un servidor de base de datos.

Verifica también que Django encuentre las plantillas y archivos estáticos de la aplicación `BS`:

```text
BS/
├── templates/
│   ├── base.html
│   ├── componentes/
│   ├── cuentas/
│   └── publica/
└── static/
    ├── css/
    ├── img/
    └── js/
```

En `settings.py`, `BS` debe aparecer en `INSTALLED_APPS`, `APP_DIRS` debe ser `True` dentro de `TEMPLATES` y `STATIC_URL` debe estar configurado. No se necesita otra carpeta `BS` dentro de `templates` o `static`.

## 5. Preparar la base de datos

```powershell
python manage.py migrate
```

Si quieres entrar al administrador de Django, crea un usuario administrador:

```powershell
python manage.py createsuperuser
```

## 6. Ejecutar el proyecto

```powershell
python manage.py check
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`. Detén el servidor con `Ctrl+C`.

Las páginas públicas acordadas usan las rutas `/`, `/acceso/`, `/registro/`, `/recuperar-clave/`, `/terminos/`, `/privacidad/`, `/politica-uso/`, `/politica-voluntariado/` y `/datos-personales/`, siempre que estén definidas en `urls.py` y tengan sus vistas correspondientes.

## Problemas frecuentes

| Error | Qué revisar |
| --- | --- |
| `No module named django` | Activa `.venv` e instala `requirements.txt`. |
| `No such file or directory: manage.py` | Ejecuta los comandos desde la carpeta donde está `manage.py`. |
| `TemplateDoesNotExist` | Comprueba las rutas dentro de `BS/templates/`, `INSTALLED_APPS` y `APP_DIRS=True`. |
| No cargan CSS o imágenes | Comprueba `{% load static %}`, las referencias `{% static 'css/archivo.css' %}` y los nombres reales de archivos en `BS/static/`. En Linux, `Logo.png` y `logo.png` son distintos. |
| `NoReverseMatch` | Comprueba los nombres de las rutas en `urls.py` usados por `{% url 'nombre' %}`. |
| `no such table` | Ejecuta `python manage.py migrate`. |

## Archivos que conviene versionar

Sube a Git el código, `requirements.txt`, las plantillas, los recursos estáticos y las migraciones de la aplicación. Excluye `.venv/`, `__pycache__/`, `.env` y la base de datos local `db.sqlite3` si contiene datos de desarrollo o información personal. Añade estas rutas al archivo `.gitignore` de la raíz:

```gitignore
.venv/
__pycache__/
*.py[cod]
.env
db.sqlite3
```

Si `.venv` ya fue añadido al seguimiento de Git, ignorarlo no basta: ejecuta `git rm -r --cached .venv` y después registra el cambio con `git add .gitignore requirements.txt README_INSTALACION.md` y `git commit -m "Documentar instalacion y excluir entorno virtual"`. El comando `--cached` retira `.venv` del repositorio, pero conserva el entorno local.
