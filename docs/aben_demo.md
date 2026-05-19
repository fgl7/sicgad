# Demo institucional SICGAD para ABEN

## Objetivo

Esta demo presenta SICGAD como una plataforma institucional para la Agencia Boliviana de Energía Nuclear, orientada a centralizar información, validar datos oficiales, reducir procesos manuales, generar indicadores ejecutivos y mantener trazabilidad de carga, validación, publicación y auditoría.

Todos los datos incluidos son ficticios y fueron creados únicamente para demostración ejecutiva.

## Carga de datos demo

Crear o actualizar la demo:

```bash
python manage.py seed_aben_demo
```

Limpiar solo objetos demo ABEN conocidos y regenerarlos:

```bash
python manage.py seed_aben_demo --reset
```

El comando crea estructura institucional, usuarios, membresías, esquemas aprobados, instancias publicadas, puntos de datos, acciones de validación, auditoría básica, proyectos y configuraciones de reportes.

## Usuarios demo

La contraseña de los usuarios demo se configura fuera del repositorio y debe compartirse por un canal separado cuando se prepare una presentación.

| Usuario | Rol | Alcance |
| --- | --- | --- |
| `admin_aben` | ADMIN | Administración general ABEN |
| `cargador_cmnyr` | LOADER | Centro de Medicina Nuclear y Radioterapia El Alto |
| `cargador_cidtn` | LOADER | Centro de Investigación y Desarrollo en Tecnología Nuclear |
| `cargador_mantenimiento` | LOADER | Mantenimiento de Equipos Críticos |
| `cargador_proyectos` | LOADER | Proyectos y Convenios |
| `validador_salud_nuclear` | VALIDATOR | Medicina Nuclear y Radioterapia |
| `validador_tecnico_aben` | VALIDATOR | Investigación, irradiación, infraestructura, seguridad y cumplimiento |
| `validador_planificacion` | VALIDATOR | Gestión Institucional y Proyectos Estratégicos |
| `director_aben` | VIEWER | Autoridad institucional con alcance global |
| `seguimiento_mhe` | VIEWER | Visualizador externo mensual con alcance global |
| `auditoria_aben` | VIEWER | Seguridad, Calidad y Cumplimiento |

Los perfiles demo quedan sin cambio obligatorio de contraseña para evitar bloqueo durante la presentación.

## Estructura institucional

Sector:

- Energía Nuclear y Aplicaciones Tecnológicas

Subsectores:

- Medicina Nuclear y Radioterapia
- Investigación y Desarrollo Nuclear
- Aplicaciones Nucleares e Irradiación
- Infraestructura y Equipamiento Tecnológico
- Gestión Institucional y Proyectos Estratégicos
- Seguridad, Calidad y Cumplimiento

Entidades principales:

- Centro de Medicina Nuclear y Radioterapia El Alto
- Centro de Investigación y Desarrollo en Tecnología Nuclear
- Laboratorio de Radiofarmacia
- Planta de Irradiación Multipropósito
- Mantenimiento de Equipos Críticos
- Proyectos y Convenios
- Seguridad Radiológica Operativa

## Esquemas de datos

El comando crea seis esquemas mensuales aprobados y publicados con 12 meses de datos ficticios:

- Atenciones en Medicina Nuclear
- Producción y Distribución de Radiofármacos
- Servicios de Irradiación Multipropósito
- Mantenimiento de Equipos Críticos
- Proyectos y Convenios Estratégicos
- Cumplimiento, Seguridad y Calidad

También crea datasets auxiliares de curva programada y ejecutada para reportes de proyectos.

## KPIs disponibles

El tablero puede mostrar:

- pacientes atendidos;
- estudios PET-CT;
- sesiones de radioterapia;
- disponibilidad de equipos y planta;
- tiempo promedio de espera;
- dosis distribuidas;
- cumplimiento de calidad;
- entregas a tiempo;
- lotes irradiados;
- toneladas tratadas;
- ingresos estimados ficticios;
- cumplimiento del plan de mantenimiento;
- horas de indisponibilidad;
- alertas críticas;
- proyectos activos y en retraso;
- avance físico y financiero promedio;
- trámites pendientes;
- cumplimiento normativo;
- hallazgos abiertos y cerrados;
- personal capacitado.

## Proyectos demo

- Modernización de Gestión Digital ABEN
- Programa de Fortalecimiento de Centros de Medicina Nuclear
- Evaluación Estratégica de SMR para Bolivia
- Plan de Gestión de Activos Críticos
- Programa de Seguridad, Calidad y Cumplimiento

Cada proyecto queda aprobado y asociado a un reporte ejecutivo con curvas programada y ejecutada ficticias.

## Guion sugerido de presentación

1. Iniciar sesión como `director_aben`.
2. Mostrar el Tablero Ejecutivo ABEN y la etiqueta de entorno demostrativo.
3. Navegar por Medicina Nuclear y mostrar pacientes atendidos, disponibilidad y tiempo de espera.
4. Mostrar Radiofarmacia e Irradiación para evidenciar servicios, calidad y producción.
5. Mostrar Mantenimiento de Equipos Críticos con preventivos, correctivos, alertas e indisponibilidad.
6. Abrir Proyectos y Convenios para mostrar avances, retrasos y trámites pendientes.
7. Revisar Auditoría para evidenciar trazabilidad institucional.
8. Iniciar sesión como `cargador_cmnyr` o `validador_salud_nuclear` para explicar carga y aprobación.
9. Cerrar con el valor institucional: menos burocracia, más trazabilidad e información oficial en tiempo real.

## Advertencia

No se incluyen nombres de pacientes, historias clínicas, datos médicos personales, información real de instalaciones críticas, secretos ni credenciales reales. La información es ficticia, sobria y destinada únicamente a demostración.
