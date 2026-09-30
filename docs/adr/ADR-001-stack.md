# ADR-001: Stack tecnico

Fecha: 2026-09-29. Estado: aceptado.

## Decision
Python 3.12 + FastAPI; React 18 + Vite; PostgreSQL 16 + pgvector (datos y RAG en una sola BD);
Amazon S3 real (boto3, sin MinIO ni emuladores; ver actualizacion); Tesseract tras interfaz `OCRProvider`;
Ollama local + proveedor comercial [A ACORDAR]; BackgroundTasks de FastAPI; Docker Compose.

## Motivo
Ecosistema Python para IA/OCR; una sola BD reduce piezas; el equipo es de 3 personas con 2 semanas.

## Consecuencias
Sin cola real: si el volumen crece, migrar a Celery/RQ es un cambio local en `ingesta`.

## Actualizacion 2026-09-30: S3 real de Amazon
Se descarta MinIO. Desarrollo y demo usan un bucket real de Amazon S3, privado y con usuario IAM
de permisos minimos. PERSONA_1 lo crea y administra. Los tests usan `moto` (simulacion de S3 en
memoria solo durante pytest), nunca el bucket real.
