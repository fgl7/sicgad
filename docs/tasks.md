# Plan de tareas para construir SICGAD

Este documento describe, en orden, las tareas para construir SICGAD
basado en la lógica funcional de `docs/logic.md`.

Cada tarea incluye:

- Objetivo.
- Pasos a ejecutar (en Windows 10, sin privilegios de administrador).
- Cómo validar que la tarea quedó bien antes de pasar a la siguiente.

La idea es que avances tarea por tarea y valides cada una.

---

## Tarea 0 – Prerrequisitos

**Objetivo**  
Asegurar que el PC tiene lo mínimo necesario para empezar.

**Pasos**

- Verificar que tienes Python instalado:
  - Abre PowerShell.
  - Ejecuta: `python --version`  
    Si no funciona, prueba: `py --version`.
- Verificar que puedes instalar paquetes en el entorno de usuario:
  - Ejecuta: `python -m pip --version` (o `py -m pip --version`).

**Cómo validar**

- Debes ver un número de versión de Python (ej. `3.x.x`) y de `pip` sin errores.
- Si no aparece, será necesario que el área de TI instale Python por ti.

---

## Tarea 1 – Crear carpeta del proyecto y entorno virtual

**Objetivo**  
Tener un directorio limpio del proyecto y un entorno virtual aislado para SICGAD.

**Pasos**

- Elegir una carpeta de trabajo (por ejemplo `e:\09_SICGAD\sicgad_project`).
- En PowerShell, ubicarse en esa carpeta:
  - `cd e:\09_SICGAD\sicgad_project`
- Crear un entorno virtual (elige una de estas formas, según qué comando tengas disponible):
  - `python -m venv .env`
  - o bien: `py -m venv .env`
- Activar el entorno virtual:
  - En PowerShell: `.\.venv\Scripts\Activate.ps1`
  - Verás que el prompt se antepone con algo como `(.env)`.

**Cómo validar**

- Ejecutar: `where python`
  - Uno de los caminos debe apuntar a `...\sicgad_project\.env\Scripts\python.exe`.
- Ejecutar: `python -V`
  - Debe mostrar la versión de Python sin errores.

---

## Tarea 2 – Instalar dependencias básicas de backend

**Objetivo**  
Instalar los paquetes mínimos para iniciar el proyecto Django, manteniendo la instalación dentro del entorno virtual.

**Pasos**

Con el entorno virtual activado:

- Actualizar `pip` dentro del entorno (opcional pero recomendado):
  - `python -m pip install --upgrade pip`
- Instalar Django y librerías básicas:
  - `pip install django`
  - `pip install django-environ`
- Instalar librerías sugeridas para la lógica de SICGAD:
  - Auditoría/historial: `pip install django-simple-history`
  - Seguridad (bloqueo de login): `pip install django-axes`
  - 2FA (podrás configurarlo más adelante): `pip install django-otp`
- Para tareas en segundo plano (más adelante):
  - `pip install celery redis`

> Nota: para desarrollo local puedes usar SQLite (sin instalar nada extra).
> Más adelante, cuando el entorno de producción esté definido, se podrá agregar
> el conector específico (por ejemplo, PostgreSQL).

**Cómo validar**

- Ejecutar: `pip list`
  - Debes ver al menos: `Django`, `django-environ`, `django-simple-history`, `django-axes`, `django-otp`, `celery`, `redis`.
- Ejecutar: `python -m django --version`
  - Debe mostrar un número de versión (por ejemplo `4.x.x`) sin errores.

---

## Tarea 3 – Crear el proyecto base de Django

**Objetivo**  
Inicializar el proyecto Django que será la base de SICGAD.

**Pasos**

Con el entorno virtual activado y en la carpeta del proyecto:

- Crear un proyecto Django con una carpeta de configuración llamada `config`:
  - `django-admin startproject config .`
- Verificar que se creó la estructura típica de Django (archivos `manage.py`, `config/settings.py`, etc.).

**Cómo validar**

- Ejecutar el servidor de desarrollo:
  - `python manage.py runserver`
- Abrir en el navegador: `http://127.0.0.1:8000/`
  - Debes ver la página de bienvenida de Django (“The install worked successfully!”).
- Detener el servidor con `Ctrl + C` en la consola.

---

## Tarea 4 – Configuración básica de settings y entorno

**Objetivo**  
Organizar la configuración para poder diferenciar desarrollo y producción, usando `django-environ`.

**Pasos**

- Crear un archivo `.env` en la raíz del proyecto (al lado de `manage.py`) con contenido mínimo, por ejemplo:
  - `DEBUG=True`
  - `SECRET_KEY=poner_una_clave_segura_para_dev`
  - `ALLOWED_HOSTS=127.0.0.1,localhost`
- Modificar `config/settings.py` para leer estas variables con `django-environ`:
  - Importar `environ`.
  - Crear el objeto `env = environ.Env(...)`.
  - Cargar el archivo `.env`.
  - Reemplazar los valores fijos de `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS` por lecturas desde `env`.
- Mantener por ahora la base de datos por defecto (SQLite) para desarrollo.

**Cómo validar**

- Ejecutar: `python manage.py check`
  - Debe indicar que no hay errores de configuración.
- Ejecutar: `python manage.py runserver`
  - Abrir `http://127.0.0.1:8000/` y confirmar que la página sigue funcionando.

---

## Tarea 5 – Crear las apps principales de Django

**Objetivo**  
Crear las aplicaciones Django que reflejan los módulos definidos en `logic.md`.

Apps iniciales sugeridas:

- `accounts` – usuarios, roles, membresías por planta.
- `plants` – definición de plantas (PCS, PICP, PICL, otras).
- `schemas` – definición de tipos de dataset y columnas.
- `ingest` – carga de archivos y validación básica.
- `validation` – bandeja y flujo de aprobación.
- `kpis` (o `dashboards`) – paneles de gráficos y KPIs.
- `audit` – auditoría y logs.
- `core` (opcional) – utilidades y modelos base compartidos.

**Pasos**

Con el entorno virtual activado:

- Crear cada app con:
  - `python manage.py startapp accounts`
  - `python manage.py startapp plants`
  - `python manage.py startapp schemas`
  - `python manage.py startapp ingest`
  - `python manage.py startapp validation`
  - `python manage.py startapp kpis`
  - `python manage.py startapp audit`
  - `python manage.py startapp core` (opcional).
- Agregar cada app a `INSTALLED_APPS` en `config/settings.py`.

**Cómo validar**

- Ejecutar: `python manage.py makemigrations`
  - No deberían aparecer errores (aunque quizás no haya migraciones aún).
- Ejecutar: `python manage.py migrate`
  - Las migraciones iniciales de Django deben aplicarse sin errores.
- Ejecutar: `python manage.py runserver` para confirmar que el proyecto sigue levantando.

---

## Tarea 6 – Estructura de templates y layout base (con CDNs)

**Objetivo**  
Configurar plantillas HTML de Django con un layout base y los CDNs necesarios (sin instalar Tailwind localmente).

**Pasos**

- Crear una carpeta `templates/` en la raíz del proyecto (si no existe).
- En `config/settings.py`, configurar `TEMPLATES` para que incluya esa carpeta.
- Crear `templates/base.html` con:
  - Estructura HTML básica (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`).
  - Inclusión de Tailwind vía CDN (por ejemplo, `https://cdn.jsdelivr.net/...`).
  - Inclusión de HTMX vía CDN.
  - Inclusión de Alpine.js vía CDN.
  - `block` de contenido para que otras plantillas hereden.
- Crear `templates/partials/sidebar.html` y `templates/partials/topbar.html` (aunque sea con contenido mínimo de prueba).
- Ajustar alguna vista sencilla (por ejemplo, la página inicial) para renderizar `base.html`.

**Cómo validar**

- Crear una vista simple en alguna app (por ejemplo en `kpis.views.home`) que renderice un template `kpis/home.html` heredando de `base.html`.
- Agregar una URL simple en `config/urls.py` (ej. ruta `/home/`). 
- Ejecutar: `python manage.py runserver` y abrir `http://127.0.0.1:8000/home/`.
  - Debes ver la página con la barra superior y lateral (aunque sean muy simples).
  - Verificar en las herramientas del navegador (F12) que las librerías desde CDN se cargan sin errores.

---

## Tarea 7 – Modelo de plantas (`plants`)

**Objetivo**  
Definir el modelo básico de plantas para poder asociar datos a PCS, PICP, PICL u otras.

**Pasos**

- En `plants/models.py`, crear un modelo `Plant` con campos como:
  - `name` (nombre legible de la planta).
  - `code` (código corto, ej. `PCS`, `PICP`, `PICL`).
  - Campos opcionales: descripción, activo/no activo, etc.
- Crear y aplicar migraciones:
  - `python manage.py makemigrations plants`
  - `python manage.py migrate`
- Opcional: registrar `Plant` en el admin de Django.

**Cómo validar**

- Ejecutar: `python manage.py shell`
  - Crear una planta de prueba:
    - `from plants.models import Plant`
    - `Plant.objects.create(name="Planta de Concentración de Sales", code="PCS")`
  - Consultar:
    - `Plant.objects.all()` y verificar que aparece la planta creada.
- Alternativamente, usar el administrador de Django (`/admin`) para crear y ver plantas.

---

## Tarea 8 – Usuarios, roles y membresías (`accounts`)

**Objetivo**  
Modelar usuarios, roles (Cargador, Validador, Visualizador, Admin) y el vínculo con plantas.

**Pasos (diseño mínimo sugerido)**

- Definir si usarás el modelo de usuario por defecto o un `CustomUser` desde el inicio.
  - Recomendado: crear un `CustomUser` si necesitas campos extra (por ejemplo, flags de 2FA, must_change_password).
- En `accounts/models.py`:
  - Definir modelo de usuario (si lo personalizas).
  - Definir modelo `Role` (o usar `choices` en un campo de usuario).
  - Definir modelo `Membership` que una `User` + `Plant` + `Role` + nivel de validación (para validadores).
- Conectar `accounts` en `config/settings.py` (por ejemplo, `AUTH_USER_MODEL = "accounts.User"` si usas uno propio).
- Crear migraciones y aplicarlas.

**Cómo validar**

- Ejecutar: `python manage.py makemigrations accounts` y luego `python manage.py migrate`.
- Crear un superusuario:
  - `python manage.py createsuperuser`
- Iniciar el servidor y entrar a `/admin`:
  - Ver que `User`, `Plant`, `Membership` (o equivalentes) están visibles y puedes crear relaciones entre ellos.

---

## Tarea 9 – Modelos de esquemas y columnas (`schemas`)

**Objetivo**  
Definir las tablas lógicas que representan los esquemas y columnas que el Cargador va a crear desde el frontend.

**Pasos (modelo sugerido, puedes ajustarlo)**

- En `schemas/models.py`, definir al menos:
  - `DatasetType`:
    - `plant` (FK a `Plant`).
    - `name` (ej. “Producción diaria PICP”).
    - `version` (entero).
    - `validation_frequency` (por ejemplo, `DAILY` o `MONTHLY`).
    - campos de auditoría básicos (creado_por, creado_en, etc.).
  - `ColumnDef`:
    - `dataset_type` (FK a `DatasetType`).
    - `name` (nombre interno).
    - `label` (nombre legible).
    - `data_type` (número, texto, fecha, booleano, categórico, etc.).
    - `required` (bool).
    - reglas (rangos mínimos/máximos, regex, choices, etc., según lo que vayas a usar).
    - **Metadatos para gráficos**:
      - `unit` (unidad, texto libre: t/día, m³, kWh, etc.).
      - `axis_role` (ej. `X`, `Y`, `SERIES`, `FILTER`, combinación según diseño).
      - `default_agg` (SUM, AVG, MAX, MIN, COUNT, etc.).
      - `is_primary_kpi` (bool).
      - `display_order` (entero para ordenar en tablas y selectores).
- Crear migraciones para `schemas` y aplicarlas.

**Cómo validar**

- En `python manage.py shell`:
  - Crear un `DatasetType` y algunas `ColumnDef` asociadas.
  - Hacer consultas para verificar que puedes recuperar las columnas y sus metadatos.
- Opcional: registrar estos modelos en el admin para visualizarlos rápidamente.

---

## Tarea 10 – Vistas y formularios para crear/editar esquemas desde el frontend

**Objetivo**  
Permitir al Cargador crear y editar esquemas (columnas incluidas) desde la interfaz web, sin tocar el backend.

**Pasos (nivel funcional, no todos los detalles)**

- En `schemas/views.py`, crear vistas para:
  - Listar esquemas (`schema_list`).
  - Ver detalle de un esquema y sus columnas (`schema_detail`).
  - Crear/editar un esquema, incluyendo un formulario dinámico para columnas (`schema_edit`).
- Usar plantillas en `templates/schemas/`:
  - `schema_list.html`, `schema_detail.html`, `schema_edit.html`.
- Usar formularios normales de Django y, si quieres más dinamismo, HTMX para agregar/eliminar filas de columnas en la misma página.
- Asegurarse de que al **guardar**:
  - Se crea/actualiza el `DatasetType` correspondiente.
  - Se crean/actualizan las `ColumnDef` asociadas con sus metadatos (incluyendo unidad, rol en gráficos, etc.).

**Cómo validar**

- Crear un usuario tipo Cargador (o usar superusuario de prueba).
- Iniciar el servidor y entrar a la pantalla de esquemas.
- Crear un esquema nuevo para una planta (ej. “Producción diaria PCS”) con varias columnas.
- Guardar y comprobar que:
  - El esquema aparece en la lista.
  - Las columnas y sus metadatos quedaron guardados correctamente en la base.

---

## Tarea 11 – Módulo de carga de datos (`ingest`)

**Objetivo**  
Permitir que el Cargador descargue plantillas, suba archivos diarios y vea errores de validación.

**Pasos resumidos**

- En `ingest/models.py`, definir un modelo para representar una carga de datos (por ejemplo, `IngestJob` o `DatasetInstance`).
- Agregar campos como:
  - `dataset_type` (FK).
  - `periodo` (fecha o mes/año según corresponda).
  - `state` (DRAFT, SUBMITTED, etc. – o bien usar solo para la parte de carga).
  - referencia al archivo subido (si lo guardas) o datos en JSON.
  - resultado de validaciones (cantidad de errores, etc.).
- En `ingest/views.py`:
  - Vista para descargar plantilla (con encabezados según `ColumnDef`).
  - Vista para subir archivo y ejecutar validaciones básicas.
  - Vista de historial de envíos.
- Plantillas en `templates/ingest/`: `upload.html`, `upload_history.html`, `error_report.html`.

**Cómo validar**

- Crear un esquema sencillo (pocas columnas) y una plantilla.
- Descargar plantilla, llenarla a mano con 2–3 filas.
- Subir el archivo desde `upload.html`.
- Verificar que:
  - Se detectan errores si rompes las reglas (tipo de dato, campo obligatorio vacío).
  - El historial de envíos muestra las cargas y sus estados.

---

## Tarea 12 – Flujo de validación y estados (`validation`)

**Objetivo**  
Implementar la máquina de estados (DRAFT, SUBMITTED, VALIDATED_L1, …, PUBLISHED, LOCKED) y la bandeja de validación.

**Pasos resumidos**

- Definir en el modelo de dataset/carga un campo de estado con choices.
- Implementar lógica para:
  - Enviar un dataset (de DRAFT a SUBMITTED).
  - Aprobar/rechazar en cada nivel (L1, L2, …).
  - Publicar automáticamente al completar el último nivel requerido.
- Crear vistas en `validation/views.py`:
  - `inbox` para listar datasets pendientes del usuario actual.
  - `detail` para ver datos, comentarios y botones de aprobar/rechazar.
- Plantillas: `templates/validate/inbox.html`, `templates/validate/detail.html`.

**Cómo validar**

- Crear un esquema y cargar un dataset de prueba.
- Asignar distintos usuarios con niveles de validación.
- Simular el flujo:
  - Cargador envía dataset.
  - Validador de nivel 1 lo ve en su bandeja y aprueba.
  - Repetir con los niveles siguientes.
  - Verificar que, al llegar al último nivel, el estado pase a PUBLISHED.

---

## Tarea 13 – Panel de KPIs y gráficos (`kpis`)

**Objetivo**  
Construir la vista principal de gráficos usando ECharts y los metadatos de `ColumnDef`.

**Pasos resumidos**

- Incluir ECharts vía CDN en `base.html` o en la plantilla de KPIs.
- En `kpis/views.py`:
  - Vista que liste los `DatasetType` disponibles.
  - Vista que, dado un dataset y un periodo, devuelva:
    - Los registros de datos.
    - La lista de columnas y sus metadatos (para saber qué se puede usar en X/Y).
- En `templates/kpis/charts.html`:
  - Selectores para elegir:
    - Planta.
    - Tipo de dataset.
    - Campo para eje X.
    - Campo para eje Y.
  - Script JS que toma la selección y construye la configuración de ECharts.

**Cómo validar**

- Tener al menos un dataset publicado con datos reales de prueba.
- Abrir la vista de KPIs, elegir un campo de fecha o índice en el eje X y un campo numérico en el eje Y.
- Confirmar que el gráfico se dibuja y cambia al modificar la selección.

---

## Tarea 14 – Auditoría y logs (`audit`)

**Objetivo**  
Registrar las acciones importantes (cargas, cambios de esquema, aprobaciones, etc.) y poder consultarlas.

**Pasos resumidos**

- Configurar `django-simple-history` para modelos clave (por ejemplo, esquemas y datasets).
- Crear modelos adicionales de auditoría si lo necesitas (por ejemplo, `AuditEvent`).
- Crear vistas y plantillas en `audit` para:
  - Listar eventos (filtros por usuario, fecha, acción).
  - Ver detalle de un evento.

**Cómo validar**

- Realizar acciones en el sistema (crear esquema, cargar dataset, aprobar, etc.).
- Abrir la vista de auditoría y comprobar que:
  - Se registran acciones con fecha/hora, usuario y descripción.
  - Puedes navegar al detalle de un evento.

---

## Tarea 15 – Seguridad avanzada (2FA, rate limiting, contraseñas)

**Objetivo**  
Configurar medidas de seguridad acordes a los requerimientos (2FA para Admin/Validadores, rate limiting, cambio de contraseña obligatorio).

**Pasos resumidos**

- Integrar `django-otp` para 2FA:
  - Seguir la documentación para añadir métodos TOTP (aplicación tipo Google Authenticator).
  - Activar 2FA al menos para usuarios con roles sensibles (Admin, Validadores).
- Integrar `django-axes` para limitar intentos de login:
  - Configurar número máximo de intentos y ventana de tiempo.
- Implementar la lógica de `must_change_password`:
  - Campo en el usuario.
  - Middleware o lógica de login que fuerce a cambiar contraseña si la bandera está activa.

**Cómo validar**

- Crear un usuario de prueba con rol de Validador.
- Activar 2FA para ese usuario y comprobar que en el siguiente login se solicita el código.
- Probar varios intentos de login fallidos seguidos y verificar que la cuenta se bloquea según la configuración de `django-axes`.

---

## Notas finales

- Este plan está pensado para que avances de forma incremental, validando cada tarea antes de seguir.
- Si en algún punto una tarea resulta muy grande, puedes dividirla en subtareas más pequeñas (por ejemplo, separar “models” de “templates” y de “vistas”).
- Dado que estás en Windows 10 sin privilegios de administrador:
  - Todas las instalaciones se hacen dentro del entorno virtual con `pip`.
  - Para estilos y JS (Tailwind, HTMX, Alpine.js, ECharts) se usan **CDNs**, sin `npm` ni herramientas de build.

Cuando quieras, podemos tomar una tarea específica de este documento y empezar a ejecutarla paso a paso, ajustando detalles según lo que vaya apareciendo en tu entorno.
