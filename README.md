# Barrio Solidario

**Plataforma de Atención de Necesidades**

Proyecto académico desarrollado para la asignatura **Ingeniería de Software II** de la Universidad Espíritu Santo (UEES).

Barrio Solidario propone una plataforma web para conectar a adultos mayores y sus cuidadores con voluntarios e instituciones aliadas, facilitando el registro, la coordinación y el seguimiento de solicitudes de asistencia comunitaria.

> **Estado actual:** Sprint 2 cerrado. Se completaron las actividades de documentación, planificación, modelado y diseño funcional. La construcción del MVP continuará en el Sprint 3.

---

## Objetivo del proyecto

Diseñar y construir una aplicación accesible, segura y trazable que permita:

- Registrar usuarios de acuerdo con su rol.
- Crear solicitudes de asistencia comunitaria.
- Relacionar solicitudes con voluntarios disponibles.
- Coordinar y dar seguimiento a la atención.
- Mantener trazabilidad sobre las acciones realizadas.
- Proteger la información de los participantes.

## Caso de estudio

En muchas comunidades, las necesidades de los adultos mayores se atienden mediante comunicaciones informales que dificultan la coordinación y el seguimiento. Barrio Solidario busca organizar este proceso mediante una plataforma centralizada, con responsabilidades definidas y registro de cada actividad.

## Objetivo del repositorio

Este repositorio centraliza la documentación académica, los artefactos de análisis y diseño, los elementos de gestión Scrum y las evidencias generadas durante el proyecto. Los documentos editables se conservan en Word, Excel o PowerPoint, mientras que sus versiones de consulta y entrega se publican en PDF.

También constituye el punto de referencia para consultar la evolución del alcance, las decisiones del equipo, la planificación de los Sprints y la trazabilidad entre requisitos, historias de usuario, clases y pantallas.

## Alcance del MVP

La primera versión se limita a las funcionalidades indispensables que pueden construirse y validarse dentro del tiempo disponible:

1. **Portal público:** información general, propósito, funcionamiento, usuarios, beneficios, métricas, aliados y contacto.
2. **Registro y acceso:** creación de cuenta, inicio de sesión y recuperación o cambio de contraseña.
3. **Panel principal autenticado:** acceso básico del usuario y visualización inicial de las opciones disponibles según su rol.

Las funciones de coordinación avanzada, asignaciones, mensajería, incidencias, administración, auditoría y reportes permanecen documentadas para una versión posterior.

## Actores principales

| Actor | Participación en la plataforma |
|---|---|
| Adulto mayor | Registra solicitudes y consulta su estado. |
| Cuidador o familiar | Gestiona solicitudes en representación del adulto mayor. |
| Voluntario | Consulta necesidades y se postula para brindar asistencia. |
| Coordinación | Revisa solicitudes, asigna voluntarios y coordina atenciones. |
| Institución aliada | Apoya o canaliza solicitudes de acuerdo con su capacidad. |
| Moderación y administración | Gestiona usuarios, catálogos, incidencias, seguridad y trazabilidad. |

## Equipo del proyecto

| Integrante | Rol principal |
|---|---|
| Alex Mendoza Morante | Scrum Master |
| Víctor Tello Bravo | Product Owner |
| Kevin Carriel Bonoso | Arquitecto de software |
| Mario Luzardo Fierro | Frontend, UI/UX y accesibilidad |
| Luis Ramírez Conejo | Backend y datos |
| Luis Rodríguez Barrera | Calidad, pruebas y seguridad |

**Docente y patrocinadora académica:** Ing. Victoria García Velásquez, Mgtr., Ph. D. (c).

## Organización por Sprints

| Sprint | Enfoque principal | Estado |
|---|---|---|
| Sprint 1 | Definición del caso, actores, requisitos, historias de usuario, backlog y organización del equipo. | Completado |
| Sprint 2 | Continuidad documental, unidades de trabajo, diseño no gráfico, modelo de clases, wireframes y alcance del MVP. | Completado |
| Sprint 3 | Construcción y validación del MVP. | Siguiente etapa |
| Sprint 4 | Integración, pruebas, presentación y cierre del proyecto. | Pendiente |

## Resultados del Sprint 2

- Acta de Constitución y requerimientos actualizados.
- Documento de Visión consolidado.
- Historias de usuario revisadas y priorizadas.
- Actividades y unidades de trabajo detalladas.
- Product Backlog organizado en la herramienta de planificación.
- Diseño no gráfico del modelo Scrum.
- Modelo de clases con atributos, métodos y relaciones.
- Diagramas generales y segmentados del modelo de clases.
- Flujo general de navegación.
- Wireframes del portal público y de los módulos por rol.
- Lineamientos visuales y criterios básicos de accesibilidad.
- Trazabilidad entre requisitos, historias de usuario, clases y pantallas.
- Definición del MVP y exclusiones para una segunda versión.

## Cadena de trazabilidad

Cada elemento del diseño debe mantener una relación verificable:

**Requisito ↔ Historia de usuario ↔ Clase del sistema ↔ Pantalla**

Ejemplo:

| Requisito | Historia de usuario | Clase | Pantalla |
|---|---|---|---|
| RF-04 Registrar solicitud | HU-16 Crear solicitud de asistencia | `SolicitudAsistencia` | Registrar solicitud |

Esta relación permite comprobar que cada pantalla responde a una necesidad documentada y que cuenta con soporte dentro del modelo del sistema.

## Estructura documental del repositorio

```text
Barrio-Solidario/
├── 03 Gestion de Sprints/        # Planificación, actas y cierres de Sprint
├── 04 Evidencias/                # Capturas, validaciones y evidencias de trabajo
├── Modelos/                      # Modelos conceptuales y diagramas
├── UML/                          # Archivos PlantUML, Mermaid o exportaciones UML
├── 00 Vision General.docx/pdf    # Documento principal del proyecto
├── 01 Acta de Constitucion.*     # Constitución, roles y acuerdos
├── 02 Vision.docx/pdf            # Antecedente documental de la visión
├── 03 Especificacion de Requerimientos.*
├── 04 Modelo de Analisis.*
├── 05 Product Backlog.*
├── 06 Plan y Seguimiento.*
├── 07 Plan y Seguimiento del Sprint 2.*
├── 08 Presentacion.*             # Presentación académica del proyecto
└── S02 Plantilla_Vision_.docx    # Plantilla académica de referencia
```

> Los nombres pueden ajustarse para evitar duplicados y mantener una numeración única. Se recomienda conservar en la raíz únicamente los documentos principales y ubicar actas, evidencias, modelos y versiones anteriores en sus carpetas correspondientes.

## Documentos principales

| Código | Documento | Contenido |
|---|---|---|
| 00 | Visión General | Alcance, interesados, requisitos, historias, modelos y diseño. |
| 01 | Acta de Constitución | Equipo, roles, responsabilidades, acuerdos y herramientas. |
| 03 | Especificación de Requerimientos | Requisitos funcionales, no funcionales y reglas del sistema. |
| 04 | Modelo de Análisis | Actores, procesos, clases y relaciones principales. |
| 05 | Product Backlog | Épicas, historias de usuario, prioridad y responsables. |
| 06 | Plan y Seguimiento | Planificación general y control del proyecto. |
| 07 | Planificación del Sprint 2 | Objetivos, actividades, unidades de trabajo y resultados. |
| 08 | Presentación | Resumen ejecutivo de los Sprints 1 y 2. |

## Archivos complementarios

- **00 Visión General:** documento consolidado que reúne el alcance, los interesados, los requisitos, las historias de usuario y los modelos desarrollados.
- **02 Visión:** antecedente documental conservado para mantener el historial del proyecto.
- **05 Product Backlog.xlsx:** versión tabular utilizada para organizar y consultar épicas, historias y responsables.
- **Presentaciones:** materiales empleados para explicar el proyecto, el avance de los Sprints y la distribución del trabajo.
- **S02 Plantilla_Vision_.docx:** plantilla académica utilizada como referencia para estructurar la documentación.
- **Actas de Sprint:** registros de planificación, seguimiento, revisión, retrospectiva y cierre almacenados en `03 Gestion de Sprints`.

## Carpetas principales

### `00 Ingenieria de Software I`

Contiene antecedentes o productos de la asignatura previa que sirven como referencia para la continuidad del proyecto.

### `03 Gestion de Sprints`

Contiene la planificación de cada Sprint, las actas de reunión y cierre, las metas, las actividades, las unidades de trabajo y las retrospectivas.

### `04 Evidencias`

Contiene capturas de reuniones, registros de Jira, validaciones, entregables y otros archivos que demuestran la ejecución de las actividades.

### `Modelos`

Contiene los modelos conceptuales, de dominio, clases, relaciones y demás representaciones utilizadas durante el análisis.

### `UML`

Contiene los archivos fuente y las exportaciones de los diagramas generales y segmentados del proyecto.

## Herramientas de trabajo

- **Jira:** gestión del Product Backlog, historias de usuario, unidades de trabajo, responsables, estados y evidencias.
- **Google Meet:** reuniones de planificación y seguimiento.
- **Google Drive:** almacenamiento colaborativo de documentos.
- **Git:** control de versiones y organización de los entregables.
- **PlantUML y Mermaid:** elaboración de diagramas técnicos.
- **Herramientas de wireframing:** representación de pantallas y flujos de navegación.

## Lineamientos visuales

| Color | Uso principal |
|---|---|
| `#2A3966` | Encabezados, navegación y elementos institucionales. |
| `#C92351` | Acciones principales y elementos destacados. |
| `#FFFFFF` | Fondos y espacios de lectura. |
| `#E9EBF0` | Separadores, tarjetas y campos. |
| `#212937` | Texto principal. |

La interfaz deberá mantener contraste suficiente, navegación comprensible, etiquetas visibles y compatibilidad con diferentes tamaños de pantalla.

## Criterios de control documental

- Conservar una única versión vigente de cada documento principal.
- Registrar fecha, versión, responsable y descripción del cambio.
- Evitar archivos duplicados con nombres ambiguos como `final`, `final2` o `último`.
- Almacenar las versiones anteriores en una carpeta de histórico.
- Vincular cada evidencia con la actividad o unidad de trabajo correspondiente.
- Actualizar este README al cierre de cada Sprint.

## Próximos pasos

1. Seleccionar las historias de usuario que formarán parte del MVP.
2. Preparar la estructura inicial de la aplicación.
3. Implementar el portal público y el módulo de acceso.
4. Construir el panel principal autenticado.
5. Ejecutar pruebas funcionales, de accesibilidad y seguridad.
6. Registrar avances y evidencias en Jira y Git.

---

**Grupo IV - Ingeniería de Software II**  
**Universidad Espíritu Santo - UEES**  
**Guayaquil, Ecuador - 2026**
