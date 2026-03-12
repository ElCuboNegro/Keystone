# ADR 0003: Framework de Ejecución Dual y Pruebas "Golden Master"

## Contexto

El proyecto se encuentra en un proceso intensivo de extracción de lógica de negocio desde un sistema legacy masivo basado en bases de datos relacionales (millones de objetos SQL, vistas, procedimientos almacenados). Se ha definido que esta lógica se documentará usando BDD (Behavior-Driven Development) y se reimplementará en Python puro u otro lenguaje moderno.

Sin embargo, en las pruebas iniciales se descubrió que escribir pruebas unitarias estándar contra la reimplementación basándose únicamente en los Feature Files (BDD) **no garantiza la paridad de Input-Output (I/O) real con el motor de base de datos**.

Existen numerosos casos extremos que el código legacy maneja de forma implícita y que un test tradicional de Python puede omitir:
1. **Manejo de espacios en blanco y recortes (Trim):** Funciones como `LTRIM(RTRIM())` o comportamientos por defecto de `VARCHAR`.
2. **Casting implícito de tipos:** SQL Server puede comparar enteros con cadenas automáticamente (`1 == "1"`), mientras que lenguajes modernos son estrictos.
3. **Lógica Tri-estado (NULLs):** El manejo de `NULL` en SQL difiere fundamentalmente de `None` en Python (ej. `NULL = NULL` evalúa a `UNKNOWN`, no `True`).
4. **Fechas y Tiempos:** Funciones específicas del motor como `GETDATE()` o truncamientos de milisegundos.

Si la reimplementación no es matemáticamente idéntica al código original bajo estos casos extremos, la migración provocará fallos silenciosos en producción.

## Decisión

Implementaremos un **Framework de Ejecución Dual (Dual Execution) y Pruebas "Golden Master"** para todas las lógicas críticas portadas desde el código legacy.

El proceso estandarizado será el siguiente:
1. **Seed (Estado Inicial):** Definir un conjunto de datos representativo que cubra casos felices y casos límite (NULLs, espacios, tipos mixtos).
2. **Golden Master (Output A - Ejecución Original):** El framework de testing debe inyectar el estado inicial en un motor de base de datos efímero o transaccional (ej. Docker con SQL Server o SQLite para simulaciones), ejecutar el código SQL legacy original (procedimiento, función, script) y capturar el estado final de las tablas como la "Verdad Absoluta" (Golden Master).
3. **Reimplementación (Output B - Ejecución Nueva):** El mismo estado inicial en formato de estructura de datos (JSON, Diccionarios de Python, DataFrames) se pasa a la nueva función de Python reimplementada, la cual retorna el nuevo estado calculado.
4. **Afirmación de Paridad Estricta:** El framework debe comparar `Output A` y `Output B` bit a bit (ignorando el ordenamiento si la base de datos no lo garantiza explícitamente, pero respetando tipos de datos equivalentes, precisión de decimales y tratamiento de vacíos/NULLs).

Si `Output A != Output B`, el test falla y la reimplementación o el archivo BDD debe ajustarse. La implementación nueva nunca se considera "completa" ni segura hasta que no coincida 100% con el Golden Master.

## Consecuencias

### Positivas
- **Confianza Absoluta:** Asegura que la migración no introduce regresiones sutiles en la lógica de negocio ni en el manejo de datos sucios.
- **Descubrimiento Automático:** Obligará a los ingenieros y agentes a descubrir y documentar peculiaridades de la base de datos legacy que no estaban claras a simple vista en el código.
- **Trazabilidad:** Proporciona un artefacto matemático (el reporte de Diff) que prueba ante auditoría que el nuevo sistema hace exactamente lo mismo que el anterior.

### Negativas / Riesgos
- **Sobrecarga de Infraestructura:** Requiere levantar contenedores de base de datos o simuladores complejos durante la integración continua.
- **Tiempo de Ejecución de Pruebas:** Los tests de Golden Master son más lentos que las pruebas unitarias en memoria, ya que involucran I/O real contra una base de datos.
- **Complejidad:** La preparación de los fixtures y el mapeo de tipos de datos (SQL a Python) añade complejidad al desarrollo inicial.

## Agentes Involucrados
Se creará un nuevo rol/skill especializado: **Golden Master Validator**, responsable de generar los wrappers de ejecución dual, preparar los fixtures de datos extremos y orquestar las comparaciones `pandas.testing.assert_frame_equal` o `deepdiff`.
