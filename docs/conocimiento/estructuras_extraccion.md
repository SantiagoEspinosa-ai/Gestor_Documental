# Estructuras de extraccion

## Formatos de salida
- Fechas: `AAAA-MM-DD`. Si el documento trae `DD/MM/AAAA` o el mes en letra, se convierte.
- Anio de vigencia de la credencial: solo el anio final (`2031` si aparece `2021 - 2031`).
- Nombres: tal como aparecen, en mayusculas si asi estan; la normalizacion la hace la validacion.
- Domicilio: una sola cadena con calle, numero, colonia, codigo postal y ciudad, en ese orden.

## Evidencia
`evidencia_por_campo` indica de donde sale cada dato: `pagina_<n>` y, si ayuda, una seccion
(`pagina_1:seccion_superior`, `pagina_2:mrz`). Las paginas se numeran desde 1.

## Confianza
- 0.9 o mas: el dato se lee con claridad y encaja con su formato.
- 0.5 a 0.9: legible con dudas (borroso, parcialmente tapado) o sin formato esperado.
- Menos de 0.5: inferido o casi ilegible.
- 0 con valor `null`: el campo no aparece.

## MRZ del pasaporte
Si la zona visual y la MRZ discrepan en un dato, se extrae el de la zona visual y se anota la
discrepancia en `observaciones_visuales`.
