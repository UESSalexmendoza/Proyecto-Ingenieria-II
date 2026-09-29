-- Barrio Solidario: preparación inicial de MySQL.
-- Ejecutar una vez con un usuario autorizado, antes de `python manage.py migrate`.
-- Las tablas de Django y de la aplicación se crean con migraciones versionadas.

--setx DB_NAME=barrio_solidario
--setx DB_USER=barrio_app
--setx DB_PASSWORD=tu_contraseña_real
--setx DB_HOST=127.0.0.1
--setx DB_PORT=3306

--setx "EMAIL_HOST=smtp.gmail.com"
--setx "EMAIL_PORT=587"
--setx "EMAIL_HOST_USER=tu_correo@gmail.com"
--setx "EMAIL_HOST_PASSWORD=tu_clave_de_aplicacion"
--setx "EMAIL_FROM=tu_correo@gmail.com"
--setx "PUBLIC_BASE_URL=http://127.0.0.1:8000"

CREATE DATABASE IF NOT EXISTS barrio_solidario
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Crear un usuario de aplicación en el servidor (ejemplo para entorno local):
-- Sustituye la contraseña y ejecuta estas líneas en MySQL; no subas secretos a Git.
-- CREATE USER 'barrio_app'@'localhost' IDENTIFIED BY 'CONTRASENA_LOCAL_SEGURA';
-- GRANT ALL PRIVILEGES ON barrio_solidario.* TO 'barrio_app'@'localhost';
