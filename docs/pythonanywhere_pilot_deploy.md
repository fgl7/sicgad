# Despliegue Piloto en PythonAnywhere (SQLite)

Guia operativa para publicar el piloto de SICGAD en `pythonanywhere.com` usando:
- Django + WSGI
- Base de datos `sqlite3` (piloto)
- Datos actuales del proyecto (snapshot del `db.sqlite3` del repo)

Cuenta objetivo (ejemplo actual):
- usuario PythonAnywhere: `lfl`
- dominio esperado: `lfl.pythonanywhere.com`

Repositorio:
- `https://github.com/fgl7/sicgad.git`

## 1. Antes de empezar (local)

### 1.1 Confirmar que el snapshot de datos esta en Git
En este repo, `db.sqlite3` esta versionado en Git, por lo que al clonar en PythonAnywhere se descargan los datos del commit actual.

Validar localmente (opcional):
```powershell
git ls-files db.sqlite3
```

### 1.2 Media (archivos subidos)
La carpeta `media/` **no** esta en Git. Si quieres conservar archivos del piloto (uploads, adjuntos, etc.), debes subirla aparte.

Empaquetar en Windows (PowerShell):
```powershell
Compress-Archive -Path .\media\* -DestinationPath .\media_pilot.zip -Force
```

Si `media/` es grande, tambien puedes crear varios zips por subcarpetas.

## 2. Crear el entorno en PythonAnywhere (Bash)

Abre una consola `Bash` en PythonAnywhere y ejecuta:

```bash
cd ~
git clone https://github.com/fgl7/sicgad.git
cd ~/sicgad
```

### 2.1 Crear entorno virtual
Usa la misma version de Python que vayas a configurar en la Web app (por ejemplo `3.11`).

```bash
python3.11 -m venv ~/.virtualenvs/sicgad-pilot
source ~/.virtualenvs/sicgad-pilot/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si `python3.11` no existe en tu cuenta, usa la version disponible (ej. `python3.10`) y luego configura esa misma en la pestaña `Web`.

## 3. Configurar variables de entorno (.env)

El proyecto ya lee variables desde `~/sicgad/.env`.

Genera una clave secreta:
```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Crea el archivo `.env`:
```bash
cat > ~/sicgad/.env <<'EOF'
SECRET_KEY=REEMPLAZAR_CON_TU_SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=lfl.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://lfl.pythonanywhere.com

# Static/Media
STATIC_ROOT=/home/lfl/sicgad/staticfiles

# Seguridad HTTPS (activar para piloto)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Ajustes actuales del proyecto (opcionales, se muestran por claridad)
AUTO_INGEST_CLEANUP_ENABLED=True
OTP_TOTP_ISSUER=SICGAD
EOF
```

Reemplaza `REEMPLAZAR_CON_TU_SECRET_KEY`.

## 4. Base de datos y archivos del piloto

### 4.1 SQLite (snapshot actual)
Como `db.sqlite3` esta en Git, ya llega al clonar el repo.

Verificar:
```bash
ls -lh ~/sicgad/db.sqlite3
```

### 4.2 Subir `media/` (si aplica)
Como no hay SSH obligatorio, puedes subir `media_pilot.zip` desde:
- `Files` tab en PythonAnywhere (por ejemplo a `/home/lfl/`)

Luego descomprimir en Bash:
```bash
cd ~/sicgad
mkdir -p media
python - <<'PY'
import zipfile
zip_path = "/home/lfl/media_pilot.zip"
with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall("/home/lfl/sicgad/media")
print("media extraida")
PY
```

Nota:
- Si el zip contiene una carpeta `media/` en su raiz, revisa el resultado para evitar `media/media/...`.
- Puedes inspeccionar con `find ~/sicgad/media | head -50`.

## 5. Comandos Django para dejar listo el proyecto

Activa el entorno virtual y ejecuta:

```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```

Opcional (recomendado para revisar seguridad):
```bash
python manage.py check --deploy
```

## 6. Crear la Web App en PythonAnywhere (UI Web tab)

Esto no se puede hacer solo desde Bash: requiere configurar la web app en la pestaña `Web`.

### 6.1 Crear app web
En `Web`:
1. `Add a new web app`
2. `Manual configuration`
3. Selecciona la misma version de Python que usaste en el `venv` (ej. `Python 3.11`)

### 6.2 Configurar paths
En la Web app:
- **Source code**: `/home/lfl/sicgad`
- **Working directory**: `/home/lfl/sicgad`
- **Virtualenv**: `/home/lfl/.virtualenvs/sicgad-pilot`

### 6.3 Configurar WSGI
Abre el archivo WSGI desde la Web tab (algo como `/var/www/lfl_pythonanywhere_com_wsgi.py`) y deja algo asi:

```python
import os
import sys

project_home = "/home/lfl/sicgad"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 6.4 Static files mappings
En `Static files` agrega:
- URL: `/static/` -> Path: `/home/lfl/sicgad/staticfiles`
- URL: `/media/` -> Path: `/home/lfl/sicgad/media`

## 7. Reiniciar y probar

En la Web tab:
- Click en `Reload`

Pruebas minimas:
1. `https://lfl.pythonanywhere.com/`
2. login
3. `/kpis/`
4. `/home/` con usuario viewer puro (debe redirigir a `/kpis/`)
5. chart + boton `Presentacion`
6. carga de CSS/JS/imagenes (sin 404 en `static`)

## 8. Logs y troubleshooting

Desde `Web` tab revisa:
- error log
- server log

Tambien puedes usar Bash para revisar rapido (paths pueden variar segun nombre de app):
```bash
ls /var/log | grep pythonanywhere
tail -n 200 /var/log/*pythonanywhere*.error.log
```

Errores comunes:
- `DisallowedHost`: falta `ALLOWED_HOSTS`
- `CSRF verification failed`: falta `CSRF_TRUSTED_ORIGINS` o dominio distinto
- `Static files` sin estilos: faltan mappings o `collectstatic`
- `No module named django`: virtualenv no configurado en Web tab o dependencias no instaladas

## 9. Notas del piloto (SQLite en produccion)

Se acepta para piloto, pero con limites:
- No es ideal para alta concurrencia
- Mantener una sola instancia web (configuracion tipica de PythonAnywhere)
- Hacer backup frecuente del archivo `db.sqlite3`

Backup rapido en Bash:
```bash
cp ~/sicgad/db.sqlite3 ~/sicgad/db.sqlite3.bak.$(date +%Y%m%d_%H%M%S)
```

## 10. Actualizar el deploy despues (nuevo commit)

```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Luego:
- `Web` tab -> `Reload`

Si el nuevo snapshot de datos cambia (y quieres reemplazarlo en piloto):
- sube nuevo `db.sqlite3` manualmente (con respaldo previo), o
- usa scripts de migracion/carga definidos por el proyecto.

