# ADR-003: Proveedor de IA comercial

Fecha: 2026-09-29. Estado: ACEPTADO (2026-09-30).

## Contexto
La suscripcion de empresa a Claude no incluye acceso a la API (Console). Opciones evaluadas:
(a) activar Console de Anthropic con limite de gasto; (b) Gemini via AI Studio (gratis);
(c) Amazon Bedrock con la cuenta AWS; (d) solo modelos locales; (e) OpenRouter (recomendado al equipo).

## Decision
- **Ollama es el proveedor principal** de todas las tareas: los datos personales no salen de la
  infraestructura en el uso normal.
- **OpenRouter es el proveedor comercial**, configurado como `respaldo` en `config/modelos.yaml`.
  Una sola API key da acceso a varios modelos (Claude, Gemini, GPT, Qwen, Llama...) sin API key de
  Anthropic. API compatible con OpenAI (`https://openrouter.ai/api/v1`).
- Privacidad en cada llamada a OpenRouter: `provider.data_collection: "deny"` y retencion cero
  (`zdr: true`). Con documentos reales solo modelos de pago que lo cumplan.
- Modelos `:free` solo en desarrollo y solo con fixtures ficticios (pueden registrar o entrenar).
- Modelo de respaldo sugerido para la demo: uno rapido con vision (p. ej. Claude Haiku o Gemini Flash);
  el identificador exacto va en `.env` (`PROVEEDOR_COMERCIAL_MODELO`), no en el codigo.

## Consecuencias
- Se cumplen los 2 modelos configurables con cambio de proveedor sin tocar el flujo.
- Anadir el proveedor = una clase en `motor_ia/proveedores/` (PERSONA_2). Al ser compatible con
  OpenAI, la misma clase puede servir tambien para Ollama cambiando `base_url` y modelo.
- Coste: saldo prepago en OpenRouter; lo administra quien tenga la cuenta, nunca claves en el repo.
