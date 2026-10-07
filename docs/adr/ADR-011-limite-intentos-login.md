# ADR-011: Limite de intentos de login

Fecha: 2026-10-07. Estado: ACEPTADO (2026-10-07, PR #52).
Propone: PERSONA_1. Afecta al Contrato 2 (`docs/contratos/endpoints.md`, linea de `POST /auth/login`) y al
catalogo de errores (`docs/contratos/codigos_error.md`, codigo nuevo). No cambia el Contrato 1 ni la BD.

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| 1 | Tras 5 fallos de un usuario en 15 minutos, `429 DEMASIADOS_INTENTOS` con `Retry-After` | PERSONA_1 (`api/auth.py`) | Aceptada |
| 2 | Se cuentan los `login` fallidos de la auditoria; sin estado nuevo ni migracion | PERSONA_1 | Aceptada |
| 3 | El intento bloqueado se audita como `login` `{resultado: "bloqueado"}` y no cuenta | PERSONA_1 (API, UI y mocks) | Aceptada |

## Contexto
- La revision de seguridad detecto que `POST /auth/login` no limita los intentos: se puede probar
  contrasenas sin freno contra un usuario conocido.
- La auditoria ya registra cada intento como `login` con `{resultado: "ok" | "fallido"}` (ADR-006 1.5).

## Decision
1. Con `LOGIN_MAX_FALLIDOS` (5) o mas `login` fallidos del usuario escrito, exista o no, dentro de
   `LOGIN_VENTANA_MINUTOS` (15) y posteriores a su ultimo `ok`, la API responde `429 DEMASIADOS_INTENTOS`
   ("Demasiados intentos fallidos; vuelve a intentarlo mas tarde") con `Retry-After` en segundos: lo que
   falta para que el fallido que libera (el N-esimo mas reciente) salga de la ventana. Ajustes en `Settings`
   y en `.env.example`.
2. Bloqueado, no se busca el usuario ni se comprueba la contrasena: no hay fuerza bruta durante el bloqueo,
   y la respuesta y el tiempo son los mismos exista o no el usuario.
3. Se cuenta en la auditoria (sin estado en memoria): aguanta reinicios y varios workers, sin migracion.
4. El intento bloqueado deja `login` con `{resultado: "bloqueado"}` (la UI: "Acceso bloqueado") y no cuenta
   para el limite: insistir no alarga el bloqueo.

## Riesgo aceptado
- Al bloquear por usuario, cualquiera que conozca un nombre de usuario puede dejarlo sin entrar 15 minutos
  con 5 intentos. Para el MVP se acepta: es mejor que permitir fuerza bruta.
- Nota de PERSONA_2 en la revision: al contar por nombre de usuario, un tercero podria bloquear a
  proposito a un usuario conocido. Aceptable para el MVP.
- Evolucion: limitar por usuario e IP, o pedir un CAPTCHA tras varios fallos.

## Consecuencias
- Codigo nuevo `DEMASIADOS_INTENTOS` (429) en `codigos_error.md`, `codigos.ts`, los mensajes de la UI y los
  mocks (que aplican el mismo limite con los valores por defecto).
- Nuevo valor `bloqueado` en el detalle de `login`.
- Si se rechaza: el login sigue sin limite de intentos.
