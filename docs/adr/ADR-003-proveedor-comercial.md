# ADR-003: Proveedor de IA comercial

Fecha: 2026-09-29. Estado: ACEPTADO (2026-09-30, actualizado el mismo dia: solo modelos gratuitos).

## Contexto
La suscripcion de empresa a Claude no incluye acceso a la API (Console). Opciones evaluadas:
(a) activar Console de Anthropic con limite de gasto; (b) Gemini via AI Studio (gratis);
(c) Amazon Bedrock con la cuenta AWS; (d) solo modelos locales; (e) OpenRouter (recomendado al equipo).
El proyecto no dispone de presupuesto para IA: no se carga saldo en ningun proveedor.

## Decision
- **Ollama es el proveedor principal** de todas las tareas: los datos personales no salen de la
  infraestructura.
- **OpenRouter es el proveedor comercial, solo con modelos gratuitos (`:free`)**, configurado como
  `respaldo` en `config/modelos.yaml`. Sin saldo ni tarjeta. API compatible con OpenAI
  (`https://openrouter.ai/api/v1`).
- Los proveedores de modelos gratuitos pueden registrar o entrenar con lo que reciben, y no admiten
  retencion cero. Por eso a OpenRouter **solo se envian fixtures ficticios**, nunca documentos reales.
- Los modelos gratuitos tienen limite de peticiones por minuto y por dia: si se agota, el flujo sigue
  con Ollama. El modelo exacto (con vision y sufijo `:free`) va en `.env` (`PROVEEDOR_COMERCIAL_MODELO`).
- Responsable: **PERSONA_2** crea la cuenta gratuita y la API key en la etapa 1, dia 2, antes de la
  tarea del proveedor. Comparte la clave por canal seguro con quien la necesite; nunca en el repo.

## Consecuencias
- Se cumplen los 2 modelos configurables con cambio de proveedor sin tocar el flujo.
- Anadir el proveedor = una clase en `motor_ia/proveedores/` (PERSONA_2). Al ser compatible con
  OpenAI, la misma clase puede servir tambien para Ollama cambiando `base_url` y modelo.
- Coste cero. Si en el futuro hay datos reales, habra que pasar a un modelo de pago con retencion
  cero (nuevo ADR).
