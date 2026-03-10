# PythonAnywhere Pilot Deploy (Checklist Rapido)

Checklist corto para desplegar/actualizar SICGAD en PythonAnywhere (`lfl.pythonanywhere.com`) usando SQLite.

Guia completa:
- `docs/pythonanywhere_pilot_deploy.md`

## 0. Datos base (piloto actual)
- Repo: `https://github.com/fgl7/sicgad.git`
- Proyecto en servidor: `/home/lfl/sicgad`
- Virtualenv: `/home/lfl/.virtualenvs/sicgad-pilot`
- WSGI: `/var/www/lfl_pythonanywhere_com_wsgi.py`
- Dominio: `https://lfl.pythonanywhere.com/`

Nota:
- para cuenta gratuita, este flujo se ejecuta desde `Consoles -> Bash`
- no requiere SSH

## 1. Bash (primera vez)
```bash
cd ~
git clone https://github.com/fgl7/sicgad.git
cd ~/sicgad

python -m venv ~/.virtualenvs/sicgad-pilot
source ~/.virtualenvs/sicgad-pilot/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si el repo es privado:
- usar `git clone` normal
- ingresar usuario GitHub + token (PAT) cuando lo pida

## 2. `.env` (primera vez / revisar)
Crear `~/sicgad/.env` con minimo:
```env
SECRET_KEY=REEMPLAZAR_CON_UNA_CLAVE_REAL_Y_LARGA
DEBUG=False
ALLOWED_HOSTS=lfl.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://lfl.pythonanywhere.com
STATIC_ROOT=/home/lfl/sicgad/staticfiles
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
FILE_UPLOAD_MAX_MEMORY_SIZE=2621440
DATA_UPLOAD_MAX_MEMORY_SIZE=10485760
MAX_INGEST_UPLOAD_BYTES=10485760
MAX_SUPPORT_IMAGE_BYTES=5242880
```

Importante:
- no usar la `SECRET_KEY` de ejemplo del repo ni placeholders de desarrollo
- con el hardening actual, Django bloquea el arranque si:
  - falta `SECRET_KEY`
  - `DEBUG=False` y la `SECRET_KEY` sigue siendo de desarrollo
  - `ALLOWED_HOSTS` queda vacio
- `.env` debe existir solo en servidor; usar `.env.example` solo como plantilla

## 3. Django (Bash)
```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
```

Nota:
- si `check --deploy` o el arranque fallan por configuracion, revisar primero `.env`
- si definiste `SECURE_HSTS_SECONDS`, no deberia aparecer `security.W004`

## 4. PythonAnywhere Web tab (primera vez)

### 4.1 Crear web app
- `Web` -> `Add a new web app`
- `Manual configuration`
- Python `3.13` (igual al venv del piloto)

### 4.2 Paths
- `Source code`: `/home/lfl/sicgad`
- `Working directory`: `/home/lfl/sicgad`
- `Virtualenv`: `/home/lfl/.virtualenvs/sicgad-pilot`

## 5. WSGI (primera vez)
Reemplazar `/var/www/lfl_pythonanywhere_com_wsgi.py` por:

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

## 6. Static / Media mappings (Web tab)
- `/static/` -> `/home/lfl/sicgad/staticfiles`
- `/media/` -> `/home/lfl/sicgad/media`

Nota:
- con `DEBUG=False`, Django ya no sirve `media/` desde `config/urls.py`
- el mapping `/media/` en PythonAnywhere es obligatorio si el sistema debe exponer uploads

## 7. HTTPS (Web tab)
- `Security` -> `Force HTTPS` = `Enabled`

Validar tambien:
- el dominio final debe coincidir con `ALLOWED_HOSTS`
- el origen HTTPS final debe coincidir con `CSRF_TRUSTED_ORIGINS`

## 8. Reload y prueba
- `Web` -> `Reload`
- Probar:
  - `/`
  - login
  - logout desde formulario POST
  - `/kpis/`
  - `/home/` con viewer puro (redirige a `/kpis/`)
  - descarga de plantilla en `ingest`
  - carga valida de archivo en `ingest`
  - rechazo de archivo con extension no permitida

## 9. Logs si falla
- `Web` -> `error log`
- `Web` -> `server log`

## 10. Redeploy rapido (nuevo commit)

Antes de `git pull`, elegir estrategia para `db.sqlite3`.

### 10.A Preservar base actual del servidor
Usar cuando PythonAnywhere ya contiene datos del piloto que quieres mantener.

```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

cp db.sqlite3 ~/db.sqlite3.prod.backup.$(date +%Y%m%d_%H%M%S)
git update-index --no-skip-worktree db.sqlite3 || true
mv db.sqlite3 ~/db.sqlite3.prod.current
git pull
cp ~/db.sqlite3.prod.current ~/sicgad/db.sqlite3
git update-index --skip-worktree db.sqlite3
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
```

Luego:
- `Web` -> `Reload`

### 10.B Reemplazar base del servidor con la del repo
Usar cuando tu fuente de verdad es el `db.sqlite3` que acabas de subir al repo.

```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

cp db.sqlite3 ~/db.sqlite3.before_repo_pull.$(date +%Y%m%d_%H%M%S)
git update-index --no-skip-worktree db.sqlite3 || true
git restore db.sqlite3
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
```

Luego:
- `Web` -> `Reload`

Si el reload falla justo despues del update:
- revisar `error log`
- confirmar `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y flags HTTPS en `.env`
- confirmar que `.env` no fue reemplazado por una plantilla insegura
- confirmar que elegiste la estrategia correcta para `db.sqlite3`
- si faltan datos del modulo `projects`, datasets o cargas, revisar primero si la base activa fue preservada o reemplazada

## 11. Backup SQLite (recomendado)
```bash
cp ~/sicgad/db.sqlite3 ~/sicgad/db.sqlite3.bak.$(date +%Y%m%d_%H%M%S)
```

## 12. Notas plan gratis
- la web app gratuita expira aproximadamente en `1 mes` (reactivable desde la cuenta)
- sirve para piloto, no para carga alta
