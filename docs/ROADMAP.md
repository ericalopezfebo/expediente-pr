# Hoja de ruta

## Fase 1 — Fundamentos

- API de expedientes, relaciones y tareas.
- Cómputo provisional de términos con explicación.
- Pruebas y CI.
- Modelo de amenazas y límites de uso.

## Fase 2 — Persistencia y acceso

- [x] SQLite para desarrollo y PostgreSQL mediante Docker.
- [x] Contexto obligatorio de bufete.
- [x] Registro inicial de auditoría.
- [x] Migraciones versionadas.
- [x] Usuarios, tokens hash y roles básicos.
- [ ] Autenticación multifactor, recuperación y rotación de credenciales.
- [ ] Bitácora append-only protegida a nivel de base de datos.
- Búsqueda y filtros.

## Fase 3 — Documentos

- Carga segura, OCR, etiquetas y versiones.
- Plantillas DOCX y generación controlada.
- Integración local opcional con VELUM.

## Fase 4 — Términos de Puerto Rico

- Reglas versionadas de procedimiento civil y administrativo.
- Feriados de Puerto Rico y calendarios judiciales.
- Autoridades citadas y pruebas de casos límite.
- Confirmación obligatoria por abogado.

## Fase 5 — Interfaz y colaboración

- Panel del bufete y cronología del caso.
- Calendario, alertas y asignaciones.
- Detección explicable de expedientes relacionados.
