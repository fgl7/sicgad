# SICGAD – Visión general funcional

SICGAD (Sistema Integral de Carga, Gestión y Análisis de Datos) es una
plataforma web basada en Django que permite:

- Cargar diariamente datos de producción de distintas plantas (PCS, PICP, PICL, etc.).
- Validar esos datos con un flujo de aprobación por niveles y por planta.
- Publicar y visualizar datos confiables para la operación diaria y para la certificación mensual.
- Mantener trazabilidad y auditoría de todo lo que se carga, aprueba o modifica.

El sistema será usado principalmente por Yacimientos de Litio Bolivianos (YLB)
y el Ministerio de Hidrocarburos y Energías (MHE) para:

- Seguimiento diario de producción.
- Certificación mensual de producción con fines de pago de regalías.
- Seguimiento del desempeño productivo y eficiencia de cada planta.

---

## Tipos de usuarios y permisos

El sistema define distintos roles, con permisos claros y alcance por planta:

- **Cargador**
  - Crea esquemas de datos para su(s) planta(s).
  - Carga datos diarios (sube archivos, revisa errores, corrige y reenvía).
  - Puede ver datos y gráficos en estado borrador y publicados, pero solo de sus plantas.

- **Validador**
  - Revisa y aprueba o rechaza datasets cargados por los Cargadores.
  - Existe una jerarquía de validadores (ej.: Jefe de Planta → Gerencia → MHE).
  - Puede ver borradores y datos publicados de las plantas donde tiene permiso.

- **Visualizador**
  - Solo ve KPIs y gráficos de datos ya publicados (oficiales).
  - Pensado para autoridades de YLB/MHE u otros invitados.

- **Administrador**
  - Crea usuarios y asigna roles, plantas y niveles de validación.
  - Define la estructura de la jerarquía de validación.
  - No publica datasets ni realiza carga de datos.
  - Tiene alcance global sobre todas las plantas.

- **Superadmin**
  - Usuario técnico creado con `createsuperuser` en Django.
  - Tiene acceso al admin de Django.
  - Crea al Administrador y realiza configuraciones de más alto nivel.

Además:

- Cada usuario tiene permisos ligados a una planta y a un rol.
- En el caso de los validadores, también tiene un nivel de validación (1, 2, 3, etc.).
- Un nivel de validación solo se habilita cuando el nivel anterior aprueba.

Seguridad recomendada:

- Autenticación de dos factores (2FA) al menos para Admin y Validadores.
- Cambio de contraseña obligatorio en el primer inicio de sesión.
- Limitación de intentos de acceso (rate limiting).
- Registros de accesos e IPs, especialmente para acciones administrativas.

---

## Flujo general de los datos

A nivel funcional, el ciclo de vida de los datos sigue estos pasos:

1. Definición de esquemas de datos.
2. Carga diaria de datos.
3. Validación diaria (operativa).
4. Publicación y visualización.
5. Consolidación y certificación mensual.
6. Cálculo de desempeño (rendimiento/eficiencia) y balances.
6. Auditoría y trazabilidad.

Cada paso se describe a continuación en lenguaje sencillo.

---

## 1. Definición de esquemas de datos

En lugar de crear tablas nuevas en la base de datos cada vez que cambian los
campos, el sistema define “esquemas lógicos” versionados.

Ideas clave:

- Para cada planta y tipo de información se define un **tipo de dataset**
  (por ejemplo: “Producción diaria PICP”).
- Ese tipo de dataset tiene:
  - Una **versión** (1, 2, 3, …).
  - Una lista de **columnas** (nombre, tipo de dato, si es obligatorio, rangos válidos, etc.).
- La creación, edición y eliminación de estas columnas se realiza **desde el frontend**:
  - El usuario trabaja en formularios de la interfaz web (agrega columnas, cambia nombres,
    tipos, reglas, etc.).
  - El backend de Django recibe esa definición de forma flexible y la guarda como
    configuración (por ejemplo, en tablas de “esquemas” y campos JSON), sin necesidad
    de crear ni modificar modelos o tablas físicas cada vez.
- Cuando es necesario agregar, editar o eliminar columnas:
  - El Cargador arma la propuesta de cambios desde el frontend y la envía con una justificación.
  - El Administrador revisa y aprueba o rechaza la solicitud.
  - Si aprueba, se crea una nueva **versión** del esquema (por ejemplo, pasa de v1 a v2).
  - Los datos antiguos mantienen su versión y siguen siendo legibles.

Beneficio:

- Se puede cambiar la estructura de los datos desde la interfaz web, sin tocar el código
  del backend ni hacer despliegues complicados. Todo se controla por versiones de esquema.

### Metadatos recomendados por columna (para gráficos y KPIs)

Para poder graficar y calcular KPIs de forma flexible, cada columna del esquema debería
guardar algunos metadatos adicionales:

- **Tipo de dato**: número, texto, fecha/hora, booleano, categórico, etc.
- **Unidad** (opcional): por ejemplo, t/día, m³, kWh, %. Sirve para mostrarla en el eje Y y en tooltips.
- **Rol en gráficos**: si el campo puede usarse como eje X, eje Y, serie, filtro, o combinación de ellos.
- **Tipo de agregación por defecto** (para KPIs): suma, promedio, máximo, mínimo, conteo, etc.
- **Es KPI principal**: marca si el campo es un indicador clave que debería aparecer por defecto en el dashboard.
- **Orden sugerido**: para decidir en qué orden se muestran las columnas en tablas y selectores.

Igual que el resto de la definición, estos metadatos se configuran **desde el frontend**
cuando el Cargador arma o edita el esquema; el backend solo los almacena y los usa para
alimentar las pantallas de gráficos y KPIs.

---

## 2. Carga diaria de datos

La carga de datos es principalmente responsabilidad de los Cargadores.

Pasos típicos:

1. El sistema genera una **plantilla Excel/CSV** basada en el esquema vigente
   (mismas columnas y tipos esperados).
2. El Cargador descarga la plantilla, la llena con los datos del día y la sube al sistema.
3. El sistema hace una **validación automática** en dos niveles:
   - Validación de estructura: si están todas las columnas, tipos correctos, campos obligatorios completados, etc.
   - Validación de reglas: rangos válidos, coherencia entre campos, etc.
4. El Cargador ve un resumen de errores (por fila y columna) y puede descargar un reporte.
5. Si hay errores corregibles, ajusta el archivo y lo vuelve a subir.
6. Una vez que pasa las validaciones, el dataset entra al flujo de aprobación.

Adicionalmente:

- Se evitan cargas duplicadas usando una firma única (planta + tipo de dataset + periodo).
- Las tareas pesadas (validaciones grandes, cálculos previos de KPIs) pueden ejecutarse en segundo plano.
- El Cargador tiene acceso a un historial de sus envíos recientes para consulta rápida.

---

## 3. Validación diaria y estados de los datos

El sistema maneja el estado de cada dataset mediante una máquina de estados.
La idea no es que el usuario vea nombres técnicos, sino que entienda en qué fase está:

- **Borrador (DRAFT)**: datos cargados pero aún en revisión del Cargador.
- **Enviado (SUBMITTED)**: datos listos para que el primer Validador los revise.
- **Validado por nivel 1 (VALIDATED L1)**: por ejemplo, validados por Jefe de Planta.
- **Validado por más niveles (L2, L3, …)**: según la jerarquía definida en cada planta.
- **Publicado (PUBLISHED)**: datos listos para alimentar tableros e informes.
- **Bloqueado (LOCKED)**: datos “congelados” que solo se pueden modificar con un proceso especial y doble aprobación.

La publicación es automática:

- Cuando el último nivel requerido para ese flujo aprueba, el dataset pasa a “Publicado”.
- El Administrador no publica manualmente; solo administra usuarios, esquemas y flujos.

---

## 4. Operación diaria vs. certificación mensual

El sistema diferencia dos tipos de procesos:

1. **Aprobación operativa diaria** (rápida).
2. **Certificación oficial mensual** (más estricta, con todos los niveles).

### 4.1 Aprobación operativa diaria

Objetivo:

- Tener datos coherentes y suficientemente confiables para la operación diaria de la planta.

Características:

- Aplica a datasets marcados como de frecuencia **diaria**.
- Luego de que el Cargador sube y corrige los datos:
  - El primer Validador operativo (ej. Jefe de Planta) los revisa.
  - Al aprobar, el sistema considera que se cumplió el flujo de validación diaria.
  - El dataset pasa a **Publicado** y alimenta los KPIs diarios (tableros de control).
- Los niveles superiores y MHE no participan en la validación diaria, evitando sobrecarga.

### 4.2 Certificación oficial mensual

Objetivo:

- Generar una tabla con la producción mensual certificada, basada en datos diarios ya publicados,
  para fines de regalías y reportes oficiales.

Funcionamiento:

- El sistema **no** espera que alguien cargue a mano una tabla mensual.
- En lugar de eso:
  - Cuando ya existen todos los días de un mes cargados y publicados,
    el sistema consolida esos datos en un **dataset mensual**.
  - La consolidación puede ser automática (por ejemplo, una tarea programada el primer
    día del mes siguiente) y calcula totales y/o promedios relevantes.
  - El dataset mensual inicia un flujo de validación más completo:
    - Cargador → Jefe de Planta → niveles superiores de YLB → MHE.
  - Cada Validador tiene un tiempo limitado (por ejemplo, un día) para aprobar o rechazar.
- Una vez que todos los niveles aprueban:
  - El estado pasa a algo equivalente a **“Producción certificada”**.
  - Esta tabla mensual certificada es la referencia oficial de producción para ese mes.

Modificaciones a datos ya certificados:

- Si se detecta un error o evento que obliga a modificar un valor de un mes:
  - El Cargador debe solicitar el cambio al Administrador con una justificación clara.
  - Las correcciones se realizan sobre los **datos diarios** (no se “parchea” la tabla mensual).
  - Toda modificación queda registrada y auditada (quién, cuándo, por qué).

---

## 5. Visualización y paneles de KPIs

El sistema de visualización se basa en un dashboard oscuro de alta densidad de información.
La idea es que los usuarios puedan ver rápidamente:

- Tendencias de producción diaria, mensual y anual.
- Comparaciones entre plantas o líneas.
- Alertas o desviaciones en variables clave.

Elementos principales:

- **Barra lateral izquierda**:
  - Menú de secciones: bandeja de validación, carga de datos, esquemas, gráficos/KPIs, auditoría, administración.
  - Permite navegar rápidamente entre módulos.

- **Encabezado superior**:
  - Título de la vista actual.
  - Selector de planta.
  - Filtros de fecha.
  - Acciones rápidas (exportar, ver borradores, etc.).

- **Zona central de contenido**:
  - Tarjetas con gráficos y KPIs.
  - Tablas de datos relevantes.
  - Listas de eventos o datasets pendientes.

Gráficos:

- Se utiliza **ECharts** para los gráficos interactivos.
- En el panel se podrá:
  - Elegir qué variables graficar (por ejemplo, elegir un campo para el eje X y otro para el eje Y).
  - Filtrar por fechas.
  - Exportar un gráfico a formato de imagen (por ejemplo, `.png`).

Estilo visual:

- Fondo oscuro (tonos azul/gris) y tarjetas ligeramente más claras.
- Colores de acento (naranja, cian, amarillo, magenta) para las series de gráficos.
- Tipografía clara y consistente.
- Estados visibles con “chips” o etiquetas de color (Borrador, Enviado, Publicado, Bloqueado).

Vistas clave:

- `validate/inbox.html`: bandeja tipo “correo” para datasets pendientes de validación.
- `kpis/charts.html`: pantalla de gráficos y KPIs, con tarjetas de indicadores numéricos.
- Otras vistas (esquemas, carga, auditoría, cuentas) reutilizan los mismos componentes visuales.

Regla importante:

- Los KPIs y gráficos públicos se alimentan **solo** con datasets en estado **Publicado**.
- Cargadores y Validadores pueden, además, ver gráficos basados en borradores de sus propias plantas
  si activan un “toggle” de borradores.

---

## 6. Trazabilidad y auditoría

La trazabilidad es un aspecto central del sistema:

- Cada acción relevante (carga, cambio de esquema, aprobación, rechazo, bloqueo, etc.)
  queda registrada con:
  - Fecha y hora.
  - Usuario que la realizó.
  - Objeto afectado (dataset, esquema, usuario).
  - Detalles adicionales (por ejemplo, motivo del cambio).

Recomendaciones funcionales:

- Mantener **logs de solo agregado** (no se borran, solo se agregan registros nuevos).
- Registrar el historial de cambios por dataset y por fila.
- Utilizar siempre **borrado lógico** (soft delete) con motivo documentado,
  y reservar el borrado físico para casos excepcionales.

Gobernanza y doble control:

- Acciones sensibles (como bloquear definitivamente datos, revertir datos bloqueados
  o borrados físicos excepcionales) requieren **doble firma**:
  - Un representante de YLB.
  - Un representante de MHE.
- Ambas firmas se guardan con fecha, hora e IP.

El diseño está pensado para que en el futuro se pueda integrar con tecnologías
tipo blockchain sin cambiar demasiado la lógica de negocio.

---

## Tecnologías y dependencias sugeridas

La siguiente lista resume las tecnologías que se ajustan a la lógica descrita
en este documento. No es definitiva, pero sirve como guía inicial.

### Backend (Django)

- **Lenguaje y framework**
  - Python 3.x.
  - Django (versión reciente LTS, por ejemplo 4.x).

- **Base de datos**
  - PostgreSQL (recomendada por su soporte para JSON y capacidades avanzadas).

- **Tareas en segundo plano**
  - Celery para ejecuciones asíncronas (validaciones grandes, consolidaciones mensuales).
  - Redis o RabbitMQ como “broker” y posiblemente Redis como backend de resultados.

- **Seguridad y autenticación**
  - `django-otp` (u otra biblioteca de 2FA) para autenticación de dos factores.
  - `django-axes` (u otra herramienta similar) para limitar intentos de login.

- **Auditoría y versionado**
  - `django-simple-history` o implementación propia para mantener historial de cambios.

- **Configuración y utilidades**
  - `django-environ` o similar para manejar variables de entorno.

### Frontend

- **Plantillas e interacción**
  - Plantillas de Django como base.
  - HTMX para interacciones dinámicas ligeras sin necesidad de SPA completo.
  - Alpine.js para lógica de interfaz sencilla en el navegador.

- **Estilos**
  - Tailwind CSS para definir el diseño del dashboard, tarjetas, tablas y formularios.

- **Gráficos**
  - Apache ECharts para gráficos de líneas, barras, tortas, etc.

---

## Estructura propuesta del proyecto (alto nivel)

A continuación se propone una estructura de módulos (apps) para el proyecto Django
y sus plantillas principales. Esta estructura puede ajustarse según avance el diseño,
pero sirve como mapa inicial.

### 1. Proyecto principal

Carpeta base (ejemplo `config/`):

- `config/settings.py`: configuración principal de Django.
- `config/urls.py`: enrutamiento global.
- `config/celery.py`: configuración de Celery (si se utiliza).
- `config/asgi.py` / `config/wsgi.py`: punto de entrada del servidor.

### 2. Aplicaciones Django (apps)

**a) `accounts` (usuarios y roles)**

- Gestión de usuarios (Cargador, Validador, Visualizador, Admin).
- Asignación de plantas y niveles de validación.
- Gestión de 2FA y políticas de contraseña.

**b) `plants` (plantas y unidades de negocio)**

- Información de cada planta (PCS, PICP, PICL, otras).
- Relación entre plantas y datasets.

**c) `schemas` (esquemas de datos)**

- Definición de tipos de dataset (por planta y tipo de información).
- Definición de columnas, tipos de dato y reglas de validación (gestionadas desde el frontend).
- Gestión de versiones de esquemas y solicitudes de cambio.

**d) `ingest` (carga de datos)**

- Descarga de plantillas Excel/CSV.
- Subida de archivos diarios.
- Validación de estructura y reglas.
- Historial de cargas por usuario y por esquema.

**e) `validation` (validación y flujos)**

- Bandeja de entrada de datasets pendientes por nivel de validador.
- Aprobación/rechazo con comentarios.
- Gestión de estados (borrador, enviado, validado, publicado, bloqueado).

**f) `kpis` o `dashboards` (visualización)**

- Pantallas de gráficos y KPIs principales.
- Filtros por planta, fecha y tipo de dataset.
- Exportación de gráficos a imagen o descarga de datos a CSV.

**g) `audit` (auditoría y trazabilidad)**

- Registro de eventos del sistema (logs de auditoría).
- Consultas por usuario, acción, fecha y planta.
- Vistas para revisar el historial de cambios.

**h) `core` o `common` (funciones comunes, opcional)**

- Modelos base, mixins, utilidades compartidas entre apps.

---

## Módulo de desempeño (rendimiento, eficiencia, balances y pérdidas)

Además del flujo de recolección/validación/certificación, SICGAD debe poder automatizar lo descrito en `docs/prop_desemp.docx`: cálculo recurrente de indicadores de rendimiento productivo y eficiencia de proceso, balances de materia y estimación de pérdidas para:

- Planta de Concentración de Sales (PCS).
- Planta Industrial de KCl.
- Planta Industrial de Li2CO3.

### Objetivo funcional

- Convertir datos operativos (diarios/mensuales) ya validados en indicadores mensuales comparables.
- Mantener trazabilidad completa: fórmula aplicada, parámetros (por ejemplo desfases de lote delta_t), fuentes usadas y versiones de esquema.
- Producir salidas consumibles: dashboards, alertas, y exportables (fichas/informes).

### Enfoque de implementación (integrable con lo que ya existe)

SICGAD ya tiene tres piezas que facilitan este módulo:

- **Esquemas versionados** (`DatasetType`/`ColumnDef`) para capturar variables “mínimas requeridas” sin cambios de código.
- **Instancias con estados** (`DatasetInstance`) para asegurar que los cálculos se basen en datos validados/publicados.
- **Datos publicados desnormalizados** (`PublishedDataPoint`) para consultar series y alimentar KPIs.

La implementación recomendada es agregar una app (por ejemplo `performance`) que:

1. **Catálogo de indicadores** (definiciones versionadas por planta).
2. **Catálogo de variables de desempeño (estático)**: una "plantilla" con las variables definidas por la metodología (nombres técnicos estables) y su unidad esperada.
3. **Mapeo administrable (solo Admin)**: asignación de cada variable de desempeño -> columna fuente del SICGAD (por `DatasetType`/`ColumnDef`), con agregación/transformaciones.
3. **Motor de cálculo** (calcula por mes/planta y deja un rastro reproducible).
4. **Almacenamiento de resultados** (indicadores por mes y trazas de cálculo).
5. **UI/exports** (tableros y reportes).

La idea central es separar:

- Variables e indicadores "metodológicos" (estáticos, controlados por la institución).
- Variables "capturadas" (dinámicas, pueden cambiar de nombre/versión en los esquemas).

Así, si cambian esquemas (nombres, versiones o dónde se registra una variable), el backend no cambia: el Admin actualiza el mapeo.

### Plantilla de variables (estático) + mapeo (Admin)

La plantilla de variables define llaves estables (ejemplos):

- PCS: `pcs.brine_volume`, `pcs.brine_density`, `pcs.tds`, `pcs.evaporated_volume_real`, `pcs.evaporated_volume_theoretical`, `pcs.salts_mass_total`, `pcs.pool_area_effective`.
- KCl: `kcl.feed_mass_dry`, `kcl.product_mass`, `kcl.product_kcl_grade`, `kcl.tails_mass`, `kcl.tails_k_grade`, `kcl.water_fresh_volume`, `kcl.water_recirculated_volume`, `kcl.energy_equivalent_boe`.
- Li2CO3: `lic.feed_mass_dry`, `lic.feed_li_grade`, `lic.product_mass`, `lic.product_purity`, `lic.residue_mass`, `lic.residue_li_grade`, `lic.energy_equivalent_boe`.

El Admin configura el mapeo de cada llave a una fuente del SICGAD:

- Fuente: `DatasetType` + `ColumnDef` (por ID, no por nombre).
- Periodicidad: diaria/mensual (y cómo se agrega a mes: SUM/AVG/LAST, etc.).
- Transformaciones (opcional): conversión de unidad, factores, manejo de nulos.
- Parámetros globales: `delta_t` (PCS), factores de masa seca, etc.

Operativamente esto se puede gestionar con una UI y/o una plantilla importable/exportable (CSV/Excel) para actualizar asignaciones sin tocar código.

### Datos de entrada: variables mínimas por planta

El documento `docs/prop_desemp.docx` lista variables mínimas para automatizar indicadores. En SICGAD se recomienda modelarlas como **dataset-types separados** (para mantener esquemas manejables) y con frecuencia diaria/mensual según corresponda.

**PCS (Concentración de Sales)**
- Producción y materia prima: volumen salmuera extraída (idealmente por pozo), densidad, TDS/fracción de sólidos, composición iónica mensual (Na, K, Li, Mg, Ca, Cl, SO4), masa de sales cristalizadas por tipo, altura de cristal y área efectiva por piscina.
- Operaciones: trasvases (fecha/hora), área efectiva evaporativa por piscina, volumen evaporado real.
- Consumos: combustibles/energía (GLP/eléctrica) normalizados a energía equivalente.
- Residuos/contingencias: masa de residuos por piscina, eventos climáticos y contingencias operativas.

**Planta Industrial de KCl**
- Materia prima: masa diaria por corriente (Silvinita, mixtas, halita, etc.), composición (% K2O, % humedad, % insolubles).
- Producción: producción diaria por tipo de KCl, pureza/ley.
- Consumibles: reactivos (colectores, floculantes, espumantes, ácidos), agua fresca, agua recirculada, energía equivalente.
- Residuos/pérdidas: masa de colas, ley de K en colas, eventos (derrames, fugas, paros).

**Planta Industrial de Li2CO3**
- Materia prima: sulfato de litio procesado, pureza/concentración de Li.
- Producción: masa diaria de Li2CO3 y pureza.
- Insumos/reactivos: consumos de reactivos (carbonato, cal, precipitantes, adsorbentes), agua (fresca/recirculada) y energía equivalente.
- Residuos/pérdidas: lodos/barros, contenido de Li en residuos, fallas críticas de proceso.

### Indicadores a soportar (síntesis)

El módulo debe soportar familias de indicadores como:

- **Rendimientos de producción** (PCS por "lote" con desfase delta_t; KCl y Li2CO3 respecto a materia prima procesada del mes).
- **Eficiencias de recuperación** (Li y K, comparando contenido elemental recuperado vs. contenido elemental alimentado/origen).
- **Eficiencia energética** (energía equivalente por TM de producto).
- **Agua y recirculación** (por TM y % recirculado, especialmente KCl).
- **Evaporación/cristalización** (PCS: real vs teórica; cristalizado real vs teórico con desfase delta_t).
- **Balances globales y pérdidas** (materia total: entradas vs productos + residuos + pérdidas; % de pérdida de Li/K).

### Desfases por lote (delta_t) y parámetros operativos

Algunos indicadores de PCS están definidos "por lote" (la salmuera extraída en un mes se cristaliza meses después). Para implementarlo:

- Guardar un **parámetro delta_t configurable** (por planta, y si aplica por línea/producto).
- Permitir **conversión mensual** (m -> m - delta_t) al momento de consultar fuentes.
- Versionar parámetros críticos (por ejemplo factores de ajuste estacional o factores de conversión a masa seca) para reproducibilidad.

### Cómo se integra con validación y certificación

Recomendación (para maximizar trazabilidad y reutilizar lo ya implementado):

- Tratar el "desempeño mensual" como un **resultado derivado** que se genera automáticamente **a partir de datos ya publicados/lockeados**.
- Generar un dataset mensual de indicadores (por planta) como `DatasetType` de frecuencia `MONTHLY` y **marcado como calculado** (solo lectura), con una `DatasetInstance` por mes.
- El estado del desempeño mensual se alinea al de la **certificación mensual** (si la certificación se bloquea/publica, el desempeño se recalcula y se bloquea/publica).
- Guardar una traza de cálculo que enlace: instancia de desempeño -> instancias fuente (IDs) + versión de fórmula + parámetros (delta_t, conversiones).

Esto permite auditoría institucional: ante una revisión, se puede reconstruir exactamente "qué datos y qué fórmula" produjeron cada indicador.

### Salidas: dashboards, alertas y exportables

- Dashboard de desempeño por planta: series mensuales, comparaciones, ranking y explicación de cálculo (numerador/denominador).
- Alertas por umbrales (configurables por indicador) y detección de faltantes (indicadores “no calculables” por ausencia de variables mínimas).
- Exportables: CSV/Excel y, más adelante, PDF (ficha mensual para fiscalización).


## Plantillas HTML principales

Se sugiere organizar las plantillas de la siguiente manera:

### Base y layout general

- `templates/base.html`
  - Estructura HTML principal (header, barra lateral, zona de contenido).
  - Inclusión de CSS (Tailwind) y JS global.

- `templates/partials/sidebar.html`
  - Menú lateral con enlaces a las principales secciones.

- `templates/partials/topbar.html`
  - Barra superior con título de la vista, selector de planta y filtros.

### Módulo de autenticación (`accounts`)

- `templates/accounts/login.html`
- `templates/accounts/change_password.html`
- `templates/accounts/user_list.html`
- `templates/accounts/user_form.html`

### Módulo de esquemas (`schemas`)

- `templates/schemas/schema_list.html`
- `templates/schemas/schema_detail.html`
- `templates/schemas/schema_edit.html`
- `templates/schemas/change_requests.html` (solicitudes de cambio pendientes).

### Módulo de carga (`ingest`)

- `templates/ingest/upload.html` (subida de archivos).
- `templates/ingest/upload_history.html` (historial de envíos del usuario).
- `templates/ingest/error_report.html` (detalle de errores de validación).

### Módulo de validación (`validation`)

- `templates/validate/inbox.html` (bandeja de datasets a revisar).
- `templates/validate/detail.html` (detalle de un dataset para aprobar/rechazar).

### Módulo de KPIs (`kpis` o `dashboards`)

- `templates/kpis/charts.html`
  - Vista principal de gráficos.
  - Selector de variables, rango de fechas y planta.
- `templates/kpis/export.html` (opcional, para descargas específicas).

### Módulo de auditoría (`audit`)

- `templates/audit/events.html` (lista de eventos auditados).
- `templates/audit/event_detail.html` (detalle de un evento crítico).

---
