# Politicas del proceso de onboarding

## Documentos requeridos
Una identificacion oficial vigente (credencial de elector; el pasaporte es opcional y complementario)
y un comprobante de domicilio. La lista autoritativa esta en `config/procesos.yaml`.

## Vigencia
- La identificacion debe estar vigente el dia del analisis.
- El comprobante de domicilio no debe tener mas de 90 dias de antiguedad.

## Consistencia entre documentos
Nombre completo y fecha de nacimiento deben coincidir entre identificaciones; el domicilio debe
coincidir entre la credencial y el comprobante. Diferencias solo de mayusculas, acentos o espacios
no cuentan como discrepancia. Una abreviatura (`Av.` / `Avenida`) tampoco, pero se marca para revision.

## Decision
El sistema recomienda; la decision final del expediente la toma siempre una persona revisora.
Un expediente con una alerta bloqueante sin resolver no puede aprobarse.
