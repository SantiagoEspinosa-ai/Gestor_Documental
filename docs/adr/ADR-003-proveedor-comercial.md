# ADR-003: Proveedor de IA comercial

Fecha: 2026-09-29. Estado: PENDIENTE [A ACORDAR].

## Contexto
La suscripcion de empresa a Claude no incluye acceso a la API (Console). Opciones evaluadas:
(a) activar Console de Anthropic con limite de gasto; (b) Gemini via AI Studio (gratis);
(c) Amazon Bedrock con la cuenta AWS; (d) solo modelos locales.

## Decision
Pendiente. Mientras tanto el enrutador opera solo con Ollama (`config/modelos.yaml`).
Anadir el proveedor = una clase en `motor_ia/proveedores/` + un bloque en `modelos.yaml`.
