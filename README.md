# Expediente PR

Plataforma open source de gestión de casos para abogados y bufetes de Puerto Rico.

> [!WARNING]
> Prototipo en desarrollo. Utiliza exclusivamente datos ficticios. No está autorizado
> para almacenar información confidencial ni para confirmar términos jurídicos.

## Propósito

Expediente PR busca reunir expedientes, asuntos relacionados, tareas, documentos y
términos en un sistema local-first, auditable y adaptado a la práctica puertorriqueña.
Los resultados jurídicos deben mostrar su fuente y explicación, y permanecer sujetos
a aprobación humana.

## Primera versión

- Crear y consultar expedientes.
- Vincular números de casos relacionados.
- Crear y consultar tareas por expediente.
- Calcular fechas provisionales con explicación y fuente indicada por el usuario.
- API documentada automáticamente con OpenAPI.
- Pruebas y validación continua en GitHub Actions.

## Inicio rápido

Requiere Python 3.11 o posterior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn expediente_pr.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` para probar la API.

También puede iniciarse con Docker:

```bash
docker compose up --build
```

## Validación

```bash
ruff check .
pytest -q
```

## Diseño y próximos pasos

- [Hoja de ruta](docs/ROADMAP.md)
- [Arquitectura de seguridad](docs/SECURITY-ARCHITECTURE.md)
- [Política de seguridad](SECURITY.md)
- [Guía de contribución](CONTRIBUTING.md)

## Licencia

Apache License 2.0. Consulta [LICENSE](LICENSE).

