# Barrio Solidario: inicio del MVP con Django y MySQL

## Orden de implementación

1. Configurar MySQL y conectar Django.
2. Completar el registro de usuarios con correo único, tipo de usuario y aceptación de políticas.
3. Implementar inicio y cierre de sesión, y recuperación de contraseña con enlace temporal.
4. Crear el panel privado, el perfil y el cambio de contraseña.

El portal público y las páginas legales ya preparadas sirven como base visual. Las solicitudes de asistencia, postulaciones, asignaciones y seguimiento están reservadas para la segunda versión del producto. El documento `10 MVP.pdf` define el alcance y sus criterios de aceptación.

## Archivo SQL que va a Git

Guarda `01_crear_base_mysql.sql` en `database/01_crear_base_mysql.sql` dentro del repositorio. Este script crea **solo la base de datos**; Django mantiene los scripts de tablas y cambios de estructura en `BS/migrations/` y en las migraciones de sus aplicaciones instaladas.

Desde CMD, con MySQL instalado y `mysql` disponible en PATH:

```cmd
mysql -u root -p < database\01_crear_base_mysql.sql
```

Las dos instrucciones comentadas `CREATE USER` y `GRANT` del archivo son un ejemplo opcional. Usa un usuario de aplicación distinto de `root` y una contraseña local que no publiques en Git.

## Conexión Django

Instala el controlador dentro de tu entorno virtual y regístralo en `requirements.txt`:

```cmd
.venv\Scripts\activate.bat
python -m pip install mysqlclient
python -m pip freeze > requirements.txt
```

En `BarrioSolidario/settings.py`, configura `DATABASES` para que lea las credenciales del entorno. Añade `import os` al principio si aún no está:

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "barrio_solidario"),
        "USER": os.environ.get("DB_USER", "barrio_app"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}
```

En **la misma ventana de CMD** donde ejecutarás Django, define tus credenciales locales:

```cmd
set DB_NAME=barrio_solidario
set DB_USER=barrio_app
set DB_PASSWORD=TU_CONTRASENA_LOCAL
set DB_HOST=127.0.0.1
set DB_PORT=3306
```

`set` dura solo durante esa sesión de CMD. No escribas tu contraseña real en archivos versionados. Si en tu instalación MySQL el usuario está creado como `'barrio_app'@'localhost'`, verifica la conexión con `127.0.0.1` y ajusta el host/permisos del usuario si MySQL lo requiere.

## Crear tablas y ejecutar

```cmd
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sube a Git `database/01_crear_base_mysql.sql`, `requirements.txt`, `settings.py` y los archivos `BS/migrations/*.py` generados. Cada integrante clona el repositorio, prepara su propia base MySQL, instala las dependencias y ejecuta `python manage.py migrate`.

**Antes de implementar el registro**, decide cómo representaremos el correo único y los tipos de usuario. Si el proyecto ya tiene migraciones aplicadas en SQLite, cambiar a un usuario personalizado de Django puede requerir rehacer las migraciones y trasladar los datos; conviene revisar el estado real del repositorio antes de elegir el modelo.
