# Criterios de clasificacion

## Credencial de elector
Tarjeta de identificacion de tamano cartera, con fotografia del titular a la izquierda, nombre,
domicilio, clave de elector, CURP (18 caracteres), fecha de nacimiento y un anio de vigencia.
Puede presentarse solo el anverso o anverso y reverso en paginas separadas.
Se confunde con: pasaporte (ambos llevan foto y fecha de nacimiento). Diferencia: la credencial
lleva domicilio y CURP; el pasaporte no lleva domicilio y tiene zona MRZ.

## Pasaporte
Pagina de datos personales con fotografia, numero de pasaporte, nacionalidad, sexo, fechas de
expedicion y vencimiento, y dos lineas de caracteres de lectura mecanica (MRZ) al pie que empiezan
por `P<`. Si solo aparece la MRZ, sigue siendo pasaporte.

## Comprobante de domicilio
Recibo de un servicio (luz, agua, telefono, internet) o estado de cuenta. Lleva el nombre del
proveedor del servicio, el nombre del titular, el domicilio completo, una fecha de emision o un
periodo facturado, y normalmente importes. No lleva fotografia.

## Desconocido
Si el documento no encaja claramente en ninguno de los tipos configurados, la respuesta correcta es
`desconocido` con confianza baja, no el tipo mas parecido.
