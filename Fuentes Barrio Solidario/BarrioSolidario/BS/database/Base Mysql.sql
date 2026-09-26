-- Barrio Solidario: preparación inicial de MySQL.
-- Ejecutar una vez con un usuario autorizado, antes de `python manage.py migrate`.
-- Las tablas de Django y de la aplicación se crean con migraciones versionadas.

--set DB_NAME=barrio_solidario
--set DB_USER=barrio_app
--set DB_PASSWORD=tu_contraseña_real
--set DB_HOST=127.0.0.1
--set DB_PORT=3306

--set "EMAIL_HOST=smtp.gmail.com"
--set "EMAIL_PORT=587"
--set "EMAIL_HOST_USER=tu_correo@gmail.com"
--set "EMAIL_HOST_PASSWORD=tu_clave_de_aplicacion"
--set "EMAIL_FROM=tu_correo@gmail.com"
--set "PUBLIC_BASE_URL=http://127.0.0.1:8000"

CREATE DATABASE IF NOT EXISTS barrio_solidario
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Crear un usuario de aplicación en el servidor (ejemplo para entorno local):
-- Sustituye la contraseña y ejecuta estas líneas en MySQL; no subas secretos a Git.
-- CREATE USER 'barrio_app'@'localhost' IDENTIFIED BY 'CONTRASENA_LOCAL_SEGURA';
-- GRANT ALL PRIVILEGES ON barrio_solidario.* TO 'barrio_app'@'localhost';
