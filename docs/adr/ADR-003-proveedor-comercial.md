# ADR-003: Proveedor de IA comercial

Fecha: 2026-09-29. Estado: PENDIENTE [A ACORDAR].

## Contexto
La suscripcion de empresa a Claude no incluye acceso a la API (Console). Opciones evaluadas:
(a) activar Console de Anthropic con limite de gasto; (b) Gemini via AI Studio (gratis);
(c) Amazon Bedrock con la cuenta AWS; (d) solo modelos locales.

La diapositiva 13 exige en el MVP "al menos 2 modelos de IA configurables". Ese requisito **no
depende de esta decision**: se cumple con dos modelos locales de Ollama (`ollama_vision` y
`ollama_texto` en `config/modelos.yaml`), asignados por tarea y con respaldo cruzado.

## Decision
Pendiente. Mientras tanto el enrutador opera con los dos modelos locales.
Anadir el proveedor = una clase en `motor_ia/proveedores/` + un bloque en `modelos.yaml`.
