# Gestor Documental Inteligente con IA

Componente configurable, reutilizable e integrable para recibir, clasificar, validar y consolidar documentos por folio.

## Estructura
```
backend/        FastAPI (Python 3.12)
  app/schemas/  Contrato 1: JSON de resultado por documento
  app/modulos/  ingesta, configuracion, orquestador, motor_ia, validacion, expediente, rag, api
frontend/       React + Vite
config/tipos/   Fichas YAML de tipos documentales (sin tocar codigo)
config/modelos.yaml  Enrutador de modelos por tarea
prompts/        Prompts versionados (nunca incrustados en codigo)
docs/adr/       Decisiones de arquitectura
docs/arquitectura.md  Arquitectura: monolito modular con puertos y adaptadores (ADR-005)
docs/contratos/ Contrato 2: endpoints
scripts/        generar_fixtures.py y utilidades
fixtures/       Documentos ficticios de prueba (nunca datos reales)
```

## Arranque
```bash
cp .env.example .env   # rellenar con claves reales, NUNCA commitear .env
docker compose up --build                   # Ollama instalado en el equipo
docker compose --profile ollama up --build  # o Ollama en un contenedor
```
`OLLAMA_BASE_URL` vale por defecto `http://host.docker.internal:11434` (Ollama instalado en el equipo);
con el perfil `ollama`, cambialo a `http://ollama:11434` (ver `.env.example`).

## Reglas del equipo
- Contratos (schemas, endpoints, interfaz del motor) solo cambian con un ADR y aviso al equipo.
- Secretos solo en `.env` o gestor de secretos. Placeholders `TU_CLAVE_AQUI` en ejemplos.
- Datos ficticios siempre. Nada real en fixtures, tests, logs ni chats con IA.
- Definicion de hecho: funciona e2e, tiene test, esta documentado, no expone secretos ni datos reales.
- Trunk-based, ramas cortas por modulo, conventional commits (`feat(ingesta): ...`).
