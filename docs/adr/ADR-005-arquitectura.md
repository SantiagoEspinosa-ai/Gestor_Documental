# ADR-005: Arquitectura de software - monolito modular con puertos y adaptadores

Fecha: 2026-09-30. Estado: ACEPTADO.

## Contexto
3 personas, 2 semanas, trabajo en paralelo por modulos contra stubs. El sistema depende de servicios
externos intercambiables (S3, Ollama, OpenRouter, Tesseract) y el repo ya separa `modulos/` y define
interfaces (`ProveedorLLM`, `OCRProvider`).

## Decision
Monolito modular (una sola aplicacion FastAPI) con puertos y adaptadores:
- Cada modulo de `backend/app/modulos/` es independiente y expone solo su `servicio.py`.
- Todo servicio externo se usa a traves de una interfaz (puerto) y una clase que la implementa
  (adaptador). Cambiar de proveedor = cambiar de adaptador.
- Reglas de dependencia en `docs/arquitectura.md`. Se documentan y se revisan en code review;
  no se comprueban automaticamente (sin import-linter en el MVP).

## Alternativas descartadas
- Microservicios: demasiada infraestructura para 3 personas y 2 semanas.
- Clean Architecture completa: demasiadas capas y codigo repetido para un MVP.
- Capas clasicas sin puertos: acopla la logica a S3, Ollama y Tesseract.

## Consecuencias
- Paralelismo: cada persona trabaja en su modulo; los stubs son adaptadores falsos del mismo puerto.
- Sin cambios en los contratos ni en las rutas de ficheros ya previstas en los prompts.
- Si en el futuro hace falta escalar, un modulo con puertos claros se puede extraer a servicio aparte.
