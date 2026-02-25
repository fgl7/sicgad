# PythonAnywhere Pilot Deploy (Checklist Rápido)

Checklist corto para desplegar/actualizar SICGAD en PythonAnywhere (`lfl.pythonanywhere.com`) usando SQLite.

Guía completa:
- `docs/pythonanywhere_pilot_deploy.md`

## 0. Datos base (piloto actual)
- Repo: `https://github.com/fgl7/sicgad.git`
- Proyecto en servidor: `/home/lfl/sicgad`
- Virtualenv: `/home/lfl/.virtualenvs/sicgad-pilot`
- WSGI: `/var/www/lfl_pythonanywhere_com_wsgi.py`
- Dominio: `https://lfl.pythonanywhere.com/`

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

Si repo privado:
- `git clone` normal y usar usuario GitHub + token (PAT) cuando lo pida.

## 2. `.env` (primera vez / revisar)
Crear `~/sicgad/.env` con mínimo:
```env
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=lfl.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://lfl.pythonanywhere.com
STATIC_ROOT=/home/lfl/sicgad/staticfiles
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

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
- `security.W004` (HSTS) puede salir como warning y no bloquea el piloto.

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

## 7. HTTPS (Web tab)
- `Security` -> `Force HTTPS` = `Enabled`

## 8. Reload y prueba
- `Web` -> `Reload`
- Probar:
  - `/`
  - login
  - `/kpis/`
  - `/home/` con viewer puro (redirige a `/kpis/`)

## 9. Logs si falla
- `Web` -> `error log`
- `Web` -> `server log`

## 10. Redeploy rápido (nuevo commit)
```bash
cd ~/sicgad
source ~/.virtualenvs/sicgad-pilot/bin/activate

git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Luego:
- `Web` -> `Reload`

## 11. Backup SQLite (recomendado)
```bash
cp ~/sicgad/db.sqlite3 ~/sicgad/db.sqlite3.bak.$(date +%Y%m%d_%H%M%S)
```

## 12. Notas plan gratis
- Web app gratuita con expiración aproximada de `1 mes` (reactivable desde la cuenta).
- Ideal para piloto, no para carga alta.

