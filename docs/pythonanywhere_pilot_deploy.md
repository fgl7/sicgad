# Despliegue Piloto en PythonAnywhere (SQLite)

Guia operativa para publicar SICGAD en `pythonanywhere.com` usando:
- Django + WSGI
- base de datos `sqlite3` para piloto
- despliegue HTTPS con configuracion endurecida

Checklist breve:
- `docs/pythonanywhere_pilot_deploy_checklist.md`

Cuenta objetivo de referencia:
- usuario PythonAnywhere: `lfl`
- dominio esperado: `lfl.pythonanywhere.com`

Repositorio:
- `https://github.com/fgl7/sicgad.git`

## 1. Antes de empezar (local)

### 1.0 Tailwind
Si tus cambios tocaron clases Tailwind en:
- `templates/**/*.html`
- `static/js/**/*.js`
- `tailwind.config.js`

entonces regenera localmente:

```powershell
cd d:\34_other\sigad
npm run build:tailwind
```

Importante:
- este paso se hace localmente, no en PythonAnywhere
- el archivo `static/css/tailwind.generated.css` debe quedar incluido en el commit

### 1.1 Base de datos del piloto
En este repo `db.sqlite3` sigue versionado, asi que al clonar el repositorio llega el snapshot del commit actual.

Validacion local opcional:
```powershell
git ls-files db.sqlite3
```

### 1.2 `media/`
No asumas que PythonAnywhere va a recibir archivos reales subidos por Git.

Regla practica:
- el codigo crea `MEDIA_ROOT=/home/lfl/sicgad/media`
- en produccion Django no sirve `media/` por `urls.py`
- PythonAnywhere debe mapear `/media/` al directorio real

Si quieres asegurarte de que las carpetas basicas existan:
```bash
mkdir -p ~/sicgad/media/ingest/raw
mkdir -p ~/sicgad/media/ingest/historical
mkdir -p ~/sicgad/media/ingest/change_support
```

Si luego necesitas migrar archivos reales:
- subirlos manualmente desde `Files`
- o descomprimir un zip dentro de `~/sicgad/media`

## 2. Crear el entorno en PythonAnywhere (Bash)

Abre una consola `Bash` en PythonAnywhere y ejecuta:

```bash
cd ~
git clone https://github.com/fgl7/sicgad.git
cd ~/sicgad
```

Si el repo es privado:
- usar usuario GitHub + token (PAT) cuando Git lo solicite
- no incrustar el token en la URL

### 2.1 Crear entorno virtual
Usa la misma version de Python que despues configurarás en la Web app.

Caso de referencia:
- Bash: `Python 3.13.x`
- Web app: `Python 3.13`

```bash
python -m venv ~/.virtualenvs/sicgad-pilot
source ~/.virtualenvs/sicgad-pilot/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configurar variables de entorno (`.env`)

El proyecto lee configuracion desde `~/sicgad/.env`.

Genera una clave segura:
```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Crea `~/sicgad/.env`:

```bash
cat > ~/sicgad/.env <<'EOF'
SECRET_KEY=REEMPLAZAR_CON_UNA_CLAVE_REAL_Y_LARGA
DEBUG=False
ALLOWED_HOSTS=lfl.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://lfl.pythonanywhere.com

# Static
STATIC_ROOT=/home/lfl/sicgad/staticfiles

# HTTPS
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False

# Upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE=2621440
DATA_UPLOAD_MAX_MEMORY_SIZE=10485760
MAX_INGEST_UPLOAD_BYTES=10485760
MAX_SUPPORT_IMAGE_BYTES=5242880

# Ajustes operativos existentes
AUTO_INGEST_CLEANUP_ENABLED=True
OTP_TOTP_ISSUER=SICGAD
EOF
```

Importante:
- no copies `.env.example` como archivo final sin revisar valores
- no uses la `SECRET_KEY` de ejemplo ni una placeholder de desarrollo
- con el hardening actual Django bloquea el arranque si:
  - falta `SECRET_KEY`
  - `DEBUG=False` y la `SECRET_KEY` sigue siendo de desarrollo
  - `ALLOWED_HOSTS` queda vacio

## 4. Base de datos y archivos del piloto

### 4.1 SQLite
Como `db.sqlite3` esta en Git, ya llega al clonar.

Verificar:
```bash
ls -lh ~/sicgad/db.sqlite3
```

### 4.2 `media/`
Verificar estructura:
```bash
find ~/sicgad/media -maxdepth 3 -type d | sort
```

Si necesitas subir archivos reales en un zip:
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

Despues revisar:
```bash
find ~/sicgad/media | head -50
```

## 5. Comandos Django para dejar listo el proyecto

```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
```

Esperado:
- si `.env` esta bien, ambos checks deben pasar
- si fallan, revisar primero `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y flags HTTPS

## 6. Crear la Web App en PythonAnywhere (Web tab)

### 6.1 Crear app web
En `Web`:
1. `Add a new web app`
2. `Manual configuration`
3. Elegir la misma version de Python usada en el `venv`

### 6.2 Configurar paths
- `Source code`: `/home/lfl/sicgad`
- `Working directory`: `/home/lfl/sicgad`
- `Virtualenv`: `/home/lfl/.virtualenvs/sicgad-pilot`

### 6.3 Configurar WSGI
Editar `/var/www/lfl_pythonanywhere_com_wsgi.py` y dejar:

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
Agregar:
- `/static/` -> `/home/lfl/sicgad/staticfiles`
- `/media/` -> `/home/lfl/sicgad/media`

Importante:
- con `DEBUG=False`, Django ya no expone `media/` via `config/urls.py`
- el mapping `/media/` es obligatorio si el sistema debe servir uploads

### 6.5 HTTPS
En `Security`:
- PythonAnywhere ya provee HTTPS para `lfl.pythonanywhere.com`
- activar `Force HTTPS`

Validar:
- el dominio final debe estar en `ALLOWED_HOSTS`
- el origen HTTPS final debe estar en `CSRF_TRUSTED_ORIGINS`

## 7. Reiniciar y probar

En `Web`:
- click en `Reload`

Pruebas minimas:
1. `https://lfl.pythonanywhere.com/`
2. login
3. logout por formulario POST
4. `/kpis/`
5. `/home/` con viewer puro, debe redirigir a `/kpis/`
6. carga de CSS/JS/imagenes sin 404
7. descarga de plantilla en `ingest`
8. carga valida de archivo en `ingest`
9. rechazo de archivo con extension no permitida

## 8. Logs y troubleshooting

Desde `Web`:
- `error log`
- `server log`

Tambien en Bash:
```bash
ls /var/log | grep pythonanywhere
tail -n 200 /var/log/*pythonanywhere*.error.log
```

Errores comunes:
- `DisallowedHost`: falta `ALLOWED_HOSTS`
- `CSRF verification failed`: falta `CSRF_TRUSTED_ORIGINS` o el dominio/origen no coincide
- arranque bloqueado por `SECRET_KEY`: la clave no existe o sigue siendo de desarrollo
- `Static files` sin estilos: faltan mappings o `collectstatic`
- `media` con 404: falta mapping `/media/`
- `No module named django`: virtualenv mal configurado o dependencias faltantes

## 9. Notas del piloto (SQLite en produccion)

SQLite se acepta para piloto, con limites:
- no es ideal para alta concurrencia
- conviene mantener una sola instancia web
- hacer backup frecuente de `db.sqlite3`
- una cuenta gratuita puede expirar aproximadamente al mes

Backup rapido:
```bash
cp ~/sicgad/db.sqlite3 ~/sicgad/db.sqlite3.bak.$(date +%Y%m%d_%H%M%S)
```

## 10. Redeploy despues de nuevos commits

### 10.0 Antes del push (local)
Si tocaste templates/JS con clases Tailwind:

```powershell
npm run build:tailwind
```

Y sube el archivo generado:
- `static/css/tailwind.generated.css`

### 10.1 En PythonAnywhere
```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
```

Luego:
- `Web` -> `Reload`

Si falla justo despues del update:
- revisar `error log`
- revisar que `.env` siga intacto
- confirmar `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- confirmar que `Force HTTPS` siga activo

### 10.2 Si cambian datos o archivos
Si necesitas reemplazar el snapshot:
- respaldar primero `db.sqlite3`
- luego subir el archivo nuevo o ejecutar la migracion/carga definida por el proyecto

Si cambian archivos reales en `media/`:
- subirlos manualmente o sincronizarlos fuera de Git
- evitar versionar archivos sensibles o muy grandes en el repo
