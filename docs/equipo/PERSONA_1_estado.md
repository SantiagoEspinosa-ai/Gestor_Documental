# PERSONA_1 - Estado y siguientes pasos (traspaso)

Actualizado: 2026-09-30. Sirve para retomar el trabajo en otra maquina o en otro chat de Claude Code.
La especificacion completa de tareas sigue en `docs/equipo/PERSONA_1_plataforma.md`; este fichero
dice en que punto estamos y que toca ahora.

## Como retomar en la maquina nueva
1. Instalar: Git, Python 3.12 (marcar "Add python.exe to PATH") y Docker Desktop.
   En el equipo anterior Python no se pudo instalar con winget (error 1603, probable bloqueo de TI).
2. Clonar y entrar en tu rama:
   ```bash
   git clone https://github.com/SantiagoEspinosa-ai/Gestor_Documental.git
   cd Gestor_Documental
   git checkout feat/plataforma
   git config user.name "TU_NOMBRE"
   git config user.email "TU_CORREO"
   cp .env.example .env    # rellenar a mano; .env NUNCA se sube
   ```
3. Abrir Claude Code dentro del repo y pegar como primer mensaje el contenido de
   `docs/equipo/PERSONA_1_plataforma.md`, y despues: "Lee tambien `docs/equipo/PERSONA_1_estado.md`".
4. Pedir a Claude que pida permiso antes de cada cambio y explique los terminos tecnicos.

## Decisiones tomadas el 2026-09-30 (ya en `main`)
| Tema | Decision | Donde |
|---|---|---|
| Almacenamiento | Amazon S3 real, sin MinIO. Tests con `moto` (S3 simulado solo en pytest) | ADR-001, plan |
| Bucket e IAM | Los crea y administra PERSONA_1 | plan, tu prompt (tarea previa) |
| IA | Ollama principal; OpenRouter solo gratuito (`:free`) como respaldo y solo con fixtures ficticios | ADR-003 |
| Cuenta OpenRouter | La crea PERSONA_2 en la etapa 1, dia 2 | ADR-003, prompt de PERSONA_2 |
| Arquitectura | Monolito modular con puertos y adaptadores; reglas solo documentadas | ADR-005, `docs/arquitectura.md` |
| Ramas | Una por persona; la tuya es `feat/plataforma`; PR a `main` al final de cada etapa | `CLAUDE.md` |

Sin cambios: los 3 contratos congelados. ADR-004 (referencia y fecha en el expediente) solo existe
en la rama `propuesta/base-etapa0`, no en `main`: esta sin decidir.

## Que te toca hacer, en orden

### Etapa 0 (pendiente)
- [ ] Avisar al equipo: hacer `git pull` y usar cada uno su rama (`feat/motor-ia`, `feat/interfaz`).
- [ ] Decidir con el equipo que hacer con la rama `propuesta/base-etapa0` (ADR-004 incluido).
- [ ] Decidir con el equipo la maquina que ejecuta Ollama.
- [ ] Crear en la consola de AWS el bucket S3 privado, el usuario IAM con permisos minimos
      (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, sin borrar) y el CORS para
      `http://localhost:5173`. Detalle en la "Tarea previa" de tu prompt.
- [ ] Entregar las claves AWS a PERSONA_3 por canal seguro (las necesita para los e2e).

### Etapa 1 (dias 2-5), en `feat/plataforma`
Siguiente tarea: **1. `backend/app/core/config.py`** (modulo `core`). Luego las tareas 2 a 12 de tu
prompt: BD y Alembic, modelos, carga de procesos, seguridad JWT, login, folios, almacenamiento S3,
ingesta, documentos, tests y READMEs.
Entregable: archivo subido por API que aparece en el bucket S3 real y en BD en estado `pendiente`.

### Etapas 2 y 3
Como en tu prompt. Al final de cada etapa, Pull Request de `feat/plataforma` a `main`.

## Pendientes abiertos del proyecto
- ADR-004 y la rama `propuesta/base-etapa0`.
- Maquina para Ollama.
