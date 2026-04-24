# Revisión UX/UI demo ABEN

## Objetivo

Esta revisión prepara SICGAD como una demostración institucional para la Agencia Boliviana de Energía Nuclear (ABEN), con énfasis en claridad ejecutiva, navegación sobria, lenguaje institucional y ausencia de rastros visibles del piloto anterior.

Mensaje central de la demo:

> SICGAD permite que la ABEN pase de procesos manuales, datos dispersos y reportes tardíos a una gestión institucional digital, trazable, validada y orientada a decisiones ejecutivas.

## Cambios UX realizados

- Se ajustó la navegación principal para usar términos institucionales: Carga institucional, Tablero Ejecutivo, Proyectos y Convenios e Indicadores calculados.
- Se reforzó la portada y el login con la narrativa "SICGAD para ABEN" y la etiqueta de entorno demostrativo con datos ficticios.
- Se agregó en login una referencia breve a usuarios demo, sin saturar la pantalla.
- Se reemplazó lenguaje técnico visible como "dataset", "pack", "RAW", "sentencia" o "realtime" por términos más claros: conjunto de datos, lote, información cargada, decisión y registro institucional.
- Se mejoraron estados vacíos y mensajes de error en carga, validación, KPIs, proyectos, esquemas y auditoría.
- Se actualizó el copy de auditoría hacia "Trazabilidad institucional".
- Se pulió el flujo de carga histórica, carga manual, corrección de archivos y consolidación mensual.
- Se actualizó documentación operativa heredada para que describa la demo ABEN.
- Se actualizó una prueba de esquema para reflejar el nuevo copy con tildes.

## Términos heredados buscados

Se buscaron, como mínimo, los siguientes términos y variantes:

- recursos evaporíticos, recursos evaporiticos, evaporítico, evaporitico
- KCl, cloruro de potasio, potasio
- litio, carbonato de litio, Li2CO3, sulfato de litio
- salmuera, sales, silvinita, bischofita, halita
- YLB, VMEERE, MEFP
- cargador_kcl, jefe_kcl_li
- plantas, pozos, cosecha, relaves

## Resultado de limpieza

No quedan coincidencias de esos términos en pantallas, templates públicos, JS de interfaz, documentación operativa ABEN ni en el comando `seed_aben_demo`.

Permanecen coincidencias legacy internas en:

- `performance/management/commands/seed_performance_catalog.py`
- `performance/management/commands/auto_map_performance_variables.py`
- `schemas/management/commands/seed_performance_variable_schemas.py`
- `performance/services.py`
- `kpis/tests.py`
- `projects/tests.py`

Justificación: pertenecen a fórmulas, comandos y pruebas legacy del módulo de performance previo. No forman parte del recorrido de demostración ABEN ni se muestran en la interfaz revisada. Se conservaron para no romper funcionalidad histórica fuera del alcance de esta revisión.

También permanece el identificador interno `AUTHORITY_MHE` y el template `sidebar_authority_mhe.html` como nombres técnicos heredados del perfil de autoridad. El texto visible del perfil se cambió a "Visualizador autoridad institucional".

## Pantallas revisadas

- Landing
- Login
- Sidebar y navegación base
- Tablero de KPIs y vistas de autoridad/externas
- Carga institucional por archivo
- Carga histórica
- Captura manual
- Historial de cargas
- Detalle y corrección de carga
- Consolidación mensual
- Bandeja de validación
- Detalle de validación
- Resumen administrativo de validaciones
- Esquemas institucionales
- Creación de certificación mensual
- Proyectos y convenios
- Configuración de reportes
- Trazabilidad institucional

## Usuarios demo revisados

- `director_aben`
- `admin_aben`
- `cargador_cmnyr`
- `cargador_cidtn`
- `cargador_mantenimiento`
- `cargador_proyectos`
- `validador_salud_nuclear`
- `validador_tecnico_aben`
- `validador_planificacion`
- `seguimiento_mhe`
- `auditoria_aben`

Contraseña demo: `REMOVED!!!`

## Flujo recomendado de presentación

1. Iniciar sesión como `director_aben`.
2. Mostrar el Tablero Ejecutivo ABEN.
3. Navegar por Medicina Nuclear y revisar pacientes atendidos, PET/CT y radioterapia.
4. Navegar a Mantenimiento de Equipos Críticos y revisar disponibilidad, alertas y mantenimiento.
5. Navegar a Proyectos y Convenios para mostrar avance físico y financiero.
6. Usar modo presentación del tablero si corresponde.
7. Mostrar Trazabilidad institucional.
8. Iniciar sesión como `cargador_cmnyr` para demostrar carga y envío a validación.
9. Iniciar sesión como `validador_salud_nuclear` para aprobar o rechazar.
10. Cerrar con el valor institucional: menos burocracia, más trazabilidad e información oficial validada.

## Problemas pendientes

- Hay nombres internos legacy (`AUTHORITY_MHE`, `sidebar_authority_mhe`) que podrían renombrarse en una refactorización posterior. No se cambiaron para evitar impacto innecesario en rutas, contexto de navegación y permisos.
- El módulo `performance` conserva comandos y fórmulas antiguas. Si la demo ABEN usará ese módulo en vivo, conviene crear un catálogo de indicadores calculados ABEN y retirar los comandos heredados del menú o de la operación.
- Durante tests, el middleware de limpieza de ingest registra un error SQLite `database table is locked` en consola, pero la suite finaliza en OK. Es un comportamiento de concurrencia/SQLite en tests y no está relacionado con los cambios de copy.

## Comandos ejecutados

```powershell
$env:PYTHONPATH='D:\34_other_projects\sicgad\sicgad_project\venv\Lib\site-packages'; $env:DEBUG='True'; python manage.py check
```

Resultado: OK, sin issues.

```powershell
$env:PYTHONPATH='D:\34_other_projects\sicgad\sicgad_project\venv\Lib\site-packages'; $env:DEBUG='True'; python manage.py test
```

Resultado final: OK, 27 tests ejecutados.

```powershell
rg -n "evapor|KCl|litio|salmuera|YLB|VMEERE|MEFP|cloruro|potasio|silvinita|bischofita|halita|sales|pozos|cosecha|relaves|cargador_kcl|jefe_kcl_li" .
```

Resultado: sin coincidencias visibles en la demo ABEN; coincidencias restantes limitadas a performance legacy y tests, documentadas arriba.

## Nota de datos

Los datos utilizados en esta demostración son ficticios y tienen fines exclusivamente demostrativos. No incluyen nombres reales de pacientes, información médica personal, secretos, credenciales reales ni datos sensibles de instalaciones críticas.
