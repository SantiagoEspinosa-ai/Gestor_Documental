# Catalogo de codigos de alerta

Referencia comun para `Alerta.codigo` (Contrato 1). No es un contrato congelado: anadir un codigo
nuevo es libre (se anade aqui en el mismo commit); cambiar el significado de uno existente requiere ADR.

Formato: `{FAMILIA}-{NNN}`. Las alertas de reglas de los YAML usan `REG-{id_regla}` para que el
codigo coincida con `reglas_cumplidas_e_incumplidas` (diapositiva 7: `vigencia_documento`, etc.).
La severidad de las alertas `REG-` la fija la ficha YAML, no este catalogo.

| Codigo | Quien la emite | Severidad | Cuando |
|---|---|---|---|
| `CLS-001` | motor_ia | critica | Tipo declarado distinto del detectado (diapositiva 5, ejemplo pasaporte -> credencial) |
| `CLS-002` | motor_ia | preventiva | `confianza_clasificacion` < `confianza_minima_clasificacion` de la ficha |
| `VAL-001` | validacion | critica | Campo `obligatorio: true` ausente o `null` |
| `VAL-002` | validacion | preventiva | Confianza del campo < `confianza_minima_campo` de la ficha |
| `VAL-003` | orquestador (ocr) | informativa | El valor del campo se ha tomado de la MRZ porque no se leyo en la zona visual (lleva `campo`) |
| `REG-{id}` | validacion | la de la ficha | Regla del YAML incumplida (p. ej. `REG-vigencia_documento`) |
| `DUP-001` | ingesta | critica | Mismo SHA-256 ya presente en el folio (no bloquea la subida) |
| `CMP-001` | validacion (comparaciones) | critica | Un campo de `comparaciones` no coincide entre documentos del folio (va en `alertas_expediente`, una por campo; ADR-006, 2.3) |
| `EXP-001` | expediente | bloqueante | Falta un documento de `tipos_requeridos` del proceso (va en `alertas_expediente`) |
| `SYS-001` | motor_ia | critica | Fallo del proveedor principal y sin respaldo; `estado_analisis=error` |
| `SYS-002` | motor_ia | critica | JSON del modelo invalido tras el reintento de correccion |
| `SYS-003` | motor_ia | preventiva | El texto del documento supera `MAX_CARACTERES_TEXTO` y se ha recortado; los campos de las paginas finales pueden no haberse extraido |
| `SYS-005` | motor_ia | informativa | El proveedor principal fallo y el analisis se hizo con el proveedor de respaldo |
| `VIS-001` | motor_ia (extra 2) | preventiva | Baja legibilidad / resolucion |
| `VIS-002` | motor_ia (extra 2) | critica | Pagina incompleta o recortada |
| `VIS-003` | motor_ia (extra 2) | critica | Alteracion o anomalia visible |

`SYS-004`: retirado, no reutilizar.

Recomendacion por documento y global (ver `docs/equipo/PERSONA_1_plataforma.md`, etapa 2):
- alguna `bloqueante` que impide aprobar (con `aplica` distinto de `false`, regla 2.2 del ADR-006)
  -> `revision_manual` y la decision `aprobar` queda bloqueada;
- sin `critica`/`bloqueante` y confianzas sobre el minimo -> `aprobar`;
- resto -> `revision_manual`.
La IA nunca decide: `rechazar` solo es una recomendacion; la decision final es humana (regla 9).
