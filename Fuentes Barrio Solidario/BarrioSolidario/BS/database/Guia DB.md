# Barrio Solidario: inicio del MVP con Django y MySQL

## Orden de implementación

1. Configurar MySQL y conectar Django.
2. Completar el registro de usuarios con correo único, tipo de usuario y aceptación de políticas.
3. Implementar inicio y cierre de sesión, y recuperación de contraseña con enlace temporal.
4. Crear el panel privado, el perfil y el cambio de contraseña.

El portal público, las páginas legales y los módulos de solicitudes, postulaciones y coordinación forman parte de la implementación progresiva. Consulta `10 MVP.pdf` para distinguir el alcance comprometido del MVP de las ampliaciones posteriores.

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

En **CMD**, guarda las variables persistentes de Windows con estos comandos. Sustituye los valores entre `<...>` por los reales:

```cmd
setx DB_NAME "barrio_solidario"
setx DB_USER "barrio_app"
setx DB_PASSWORD "<CONTRASEÑA_DEL_USUARIO_BARRIO_APP_EN_MYSQL>"
setx DB_HOST "127.0.0.1"
setx DB_PORT "3306"

setx EMAIL_HOST "smtp.gmail.com"
setx EMAIL_PORT "587"
setx EMAIL_HOST_USER "<TU_CORREO_GMAIL>"
setx EMAIL_HOST_PASSWORD "<CLAVE_DE_APLICACION_DE_GMAIL>"
setx EMAIL_FROM "<TU_CORREO_GMAIL>"
setx PUBLIC_BASE_URL "http://127.0.0.1:8000"
```

`setx` deja las variables disponibles en **nuevas ventanas de CMD**; cierra esta ventana y abre otra antes de activar el entorno virtual y ejecutar Django. Para probarlas inmediatamente sin abrir una ventana nueva, utiliza `set "DB_NAME=barrio_solidario"` (y el mismo formato para cada variable) en la ventana actual. `set` solo dura mientras esa ventana siga abierta. Si modificas una variable con `setx` mientras el servidor está corriendo, reinicia CMD y `runserver`: el proceso conservará los valores antiguos hasta entonces.

No escribas contraseñas reales en archivos versionados. `EMAIL_HOST_PASSWORD` es la **contraseña de aplicación de Gmail para SMTP**, no el secreto del cliente OAuth de Google. Si Gmail muestra esa contraseña en grupos de cuatro caracteres, guárdala en la variable sin los espacios. La configuración de correo en `settings.py` debe leer `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `EMAIL_FROM`, utilizar TLS en el puerto 587 y definir `DEFAULT_FROM_EMAIL` con `EMAIL_FROM`. `PUBLIC_BASE_URL` sirve para construir enlaces enviados por correo. Si en MySQL el usuario existe como `'barrio_app'@'localhost'`, verifica la conexión con `127.0.0.1` y ajusta el host o los permisos si hace falta.

## Inicio de sesión con Google y Microsoft (OAuth)

Esta sección se aplica a la integración de **django-allauth** ya instalada en Barrio Solidario. El SMTP de Gmail anterior permite **enviar correos**; el cliente OAuth de Google y la aplicación de Microsoft permiten **iniciar sesión**. Son credenciales distintas y no deben intercambiarse.

### Preparación en Django

Verifica en `settings.py` que estén `django.contrib.sites`, `allauth`, `allauth.account`, `allauth.socialaccount`, `allauth.socialaccount.providers.google` y `allauth.socialaccount.providers.microsoft` en `INSTALLED_APPS`; que esté `allauth.account.middleware.AccountMiddleware` en `MIDDLEWARE`, y que `SITE_ID` corresponda al registro que usarás en **Sitios** (normalmente `SITE_ID = 1`). En `urls.py` debe existir `path("accounts/", include("allauth.urls"))`.

Para configurar clientes desde **Aplicaciones sociales** en Django Admin, registra las credenciales **allí**, sin duplicarlas como `APP` o `APPS` dentro de `SOCIALACCOUNT_PROVIDERS` para el mismo proveedor. Conserva el adaptador social y el flujo de confirmación por correo del proyecto: registrar una aplicación OAuth no concede por sí solo el rol ni omite la validación de la cuenta.

Después de `python manage.py migrate`, abre [Django Admin](http://localhost:8000/admin/) con un superusuario. En **Sitios → Sitios** (`/admin/sites/site/`), edita el sitio cuyo ID coincide con `SITE_ID`:

| Campo | Valor para desarrollo local |
| --- | --- |
| Dominio | `localhost:8000` |
| Nombre | `Barrio Solidario (local)` |

El campo **Dominio** no lleva `http://`, `https://` ni una barra final. Si también pruebas la aplicación como `127.0.0.1:8000`, puedes crear otro sitio con ese dominio, pero la aplicación social debe estar vinculada al sitio realmente seleccionado por `SITE_ID`. Para evitar inconsistencias de sesión, realiza la prueba OAuth completa entrando siempre por **`http://localhost:8000`**, especialmente con Microsoft. Si creas otro sitio y cambias `SITE_ID`, revisa también las asociaciones de ambas aplicaciones sociales.

### Google Cloud

En [Google Cloud Console](https://console.cloud.google.com/apis/credentials), selecciona el proyecto, configura la **pantalla de consentimiento OAuth** (nombre de la aplicación, correo de soporte y usuarios de prueba si la aplicación está en modo de prueba) y crea un **ID de cliente OAuth** de tipo **Aplicación web**.

| Campo en Google Cloud | Valor local |
| --- | --- |
| Orígenes autorizados de JavaScript | `http://localhost:8000` |
| URI de redirección autorizada | `http://localhost:8000/accounts/google/login/callback/` |
| URI adicional, solo si usas 127.0.0.1 | `http://127.0.0.1:8000/accounts/google/login/callback/` |

Copia el **ID de cliente** y el **secreto de cliente** generados. El URI de redirección debe coincidir exactamente con el que Django envía, incluido protocolo, host, puerto y `/` final. Si Google limita la aplicación a usuarios de prueba, agrega allí las cuentas con las que harás la prueba.

### Microsoft Entra

En [Microsoft Entra Admin Center](https://entra.microsoft.com/) entra a **Identidad → Aplicaciones → Registros de aplicaciones → Nuevo registro**. La aplicación debe pertenecer a un directorio de Entra. Si probarás cuentas de Outlook/Hotmail y cuentas de trabajo o escuela, elige **Cuentas en cualquier directorio organizativo y cuentas personales de Microsoft**. Si solo admitirás cuentas de tu organización, configura después el `tenant` correspondiente en el proveedor `microsoft` de allauth; el valor predeterminado `common` se usa para múltiples organizaciones y cuentas personales.

En **Autenticación → Agregar una plataforma**, selecciona **Web** (Django intercambia el código en el servidor; no elijas *Single-page application*) y registra:

```text
http://localhost:8000/accounts/microsoft/login/callback/
```

Este callback usa **localhost** deliberadamente para la prueba local de Microsoft. Abre también el sitio desde `http://localhost:8000`, no desde `http://127.0.0.1:8000`, al pulsar «Iniciar sesión con Microsoft». Luego, en **Certificados y secretos → Nuevo secreto de cliente**, copia inmediatamente su **Valor**. El campo «ID de secreto» no es la contraseña que requiere Django. Copia además el **Id. de aplicación (cliente)** de la página de información general. Registra la fecha de expiración del secreto para renovarlo antes de que venza.

### Aplicaciones sociales en Django Admin

En **Aplicaciones sociales → Aplicaciones sociales** (`/admin/socialaccount/socialapp/`), crea **una** aplicación por proveedor y relaciona **ambas** con el sitio local configurado arriba:

| Campo de SocialApp | Google | Microsoft |
| --- | --- | --- |
| Proveedor | `Google` | `Microsoft` |
| Nombre | `Google` | `Microsoft` |
| Client id | ID de cliente OAuth de Google | Id. de aplicación (cliente) de Entra |
| Secret key | Secreto de cliente de Google | **Valor** del secreto de cliente de Entra |
| Key | Vacío | Vacío |
| Sites | `Barrio Solidario (local)` | `Barrio Solidario (local)` |

No crees dos `SocialApp` del mismo proveedor asociadas al mismo sitio: allauth podría no saber cuál usar. El **Site** de Django no es el registro de aplicación de Microsoft: es la asociación local del dominio con las credenciales de cada proveedor. Evita publicar los secretos, exportarlos en capturas o agregarlos a Git.

### Comprobación

1. Abre una ventana nueva de CMD, activa el entorno virtual y ejecuta `python manage.py migrate` y `python manage.py runserver localhost:8000`.
2. Entra en [http://localhost:8000](http://localhost:8000) y prueba Google y Microsoft por separado desde la página de acceso.
3. Si aparece un error de **redirect URI**, compara la dirección completa que aparece en el error con el callback registrado en el proveedor. Revisa también el dominio en **Sites**, `SITE_ID` y el sitio seleccionado en cada `SocialApp`.
4. Si aparece «SocialApp matching query does not exist» o «MultipleObjectsReturned», revisa respectivamente la ausencia o duplicación de aplicaciones sociales asociadas al sitio activo.
5. Si el proveedor autentica pero Barrio Solidario exige cuenta, rol o confirmación, completa el registro y la aprobación propios del proyecto; OAuth no reemplaza esos pasos.

`PUBLIC_BASE_URL=http://127.0.0.1:8000` puede mantenerse para enlaces de correo locales, pero esos enlaces abrirán un **host distinto** de `localhost`: el navegador mantiene sesiones separadas por host. Si deseas usar el mismo host para el correo y OAuth durante las pruebas, cambia la variable a `http://localhost:8000` mediante `setx PUBLIC_BASE_URL "http://localhost:8000"`, abre un CMD nuevo y reinicia Django. En un despliegue real, sustituye ambos hosts locales por el dominio público con HTTPS y registra los nuevos callbacks en Google y Microsoft.

### Referencias oficiales

- [django-allauth: proveedor Google](https://docs.allauth.org/en/latest/socialaccount/providers/google.html).
- [django-allauth: proveedor Microsoft](https://docs.allauth.org/en/latest/socialaccount/providers/microsoft.html).
- [Microsoft: agregar una URI de redirección](https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-redirect-uri).
- [Django: framework Sites](https://docs.djangoproject.com/en/5.2/ref/contrib/sites/).

## Crear tablas y ejecutar

```cmd
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sube a Git `database/01_crear_base_mysql.sql`, `requirements.txt`, `settings.py` y los archivos `BS/migrations/*.py` generados. Cada integrante clona el repositorio, prepara su propia base MySQL, instala las dependencias y ejecuta `python manage.py migrate`.

En este proyecto el perfil y los roles complementan al usuario de Django. Antes de modificar el modelo de autenticación o una migración ya aplicada, revisa los datos y las migraciones existentes.
