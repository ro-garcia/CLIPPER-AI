# Detection Rules Manager

Abre **Settings → Moment Detection**. La instalación empieza con un diccionario vacío; no hay vocabulario dentro del extractor. Se puede importar `config/moment-rules.example.json` como ejemplo opcional. Sus frases son datos JSON editables, no lógica del detector. No se insertan automáticamente ni reaparecen tras eliminarlas.

## Reglas, grupos y perfiles

**Reglas:** nombre, patrón literal, tipo, categoría libre, peso entre −1 y +1, idioma, modo de coincidencia, grupo opcional, distinción de mayúsculas e interruptor. SQLite conserva también ID y fechas UTC de creación y actualización. Se pueden buscar por nombre, frase y categoría, y filtrar por tipo o grupo.

Tipos disponibles: KEYWORD, KEY_PHRASE, QUESTION_PATTERN, STRONG_STATEMENT, CONCLUSION, REACTION, TOPIC, WARNING, ANNOUNCEMENT y CUSTOM. No hay comportamiento especial ni frases predefinidas por tipo: son etiquetas que acompañan a la señal y permiten extender el evaluador posteriormente.

**Grupos:** permiten desactivar conjuntos enteros sin modificar los interruptores de cada regla. Al eliminar un grupo se conservan sus reglas, se dejan sin grupo y se desactivan para evitar que empiecen a actuar inesperadamente.

**Perfiles:** seleccionan la unión de todos los miembros de los grupos elegidos y las reglas individuales seleccionadas. Una regla desactivada o cuyo grupo está desactivado nunca se aplica, aunque el perfil la incluya individualmente. Un perfil sin miembros aporta cero reglas. “Todas las reglas habilitadas” elimina el filtro de perfil, pero respeta ambos interruptores. Para eliminar el perfil activo, selecciona primero otro perfil o Todas las reglas.

El selector **Detection Profile** está disponible en Settings y Live Monitor. La selección se guarda y se recupera al reiniciar.

## Coincidencias e idiomas

| Modo | Comportamiento |
| --- | --- |
| EXACT | El patrón equivale a todo el texto normalizado de la ventana |
| CONTAINS | El patrón es una subcadena literal del texto |
| STARTS_WITH | El texto comienza con el patrón |
| ENDS_WITH | El texto termina con el patrón |

Se normalizan Unicode a NFC y espacios consecutivos, y se conserva la puntuación y los acentos. Sin distinción de mayúsculas se usa `casefold`. CONTAINS también puede coincidir dentro de una palabra: no añade fronteras de palabra implícitas. Los caracteres de expresiones regulares se tratan literalmente y el modo REGEX se rechaza.

Idiomas mediante códigos, por ejemplo `es`, `en` o `fr-CA`. Una regla `fr` se aplica a textos `fr` y `fr-CA`; una regla regional `fr-CA` no se aplica indiscriminadamente a todo el francés. `*` en una regla significa universal. `*` en el texto del laboratorio significa idioma desconocido y solo activa reglas universales. En vivo se utiliza el idioma detectado por Whisper.

## Señales, no decisiones automáticas

Cada regla aporta su peso **una vez por ventana**, aunque el patrón aparezca muchas veces. Dos reglas distintas configuradas para la misma frase aportan por separado. Los pesos negativos restan. `linguistic_weight` conserva la suma y `detection_confidence` la limita al intervalo 0–1. Este valor es una puntuación heurística de señales, **no una probabilidad de viralidad**.

El laboratorio muestra coincidencias, pesos y revisión de configuración. Live Monitor muestra las señales de la ventana reciente de transcripción, aproximadamente 60 segundos con un segmento de margen. Las ventanas están limitadas además a 100 fragmentos y 20.000 caracteres. La evaluación se vuelve a calcular si cambian reglas o perfil, incluso sin audio nuevo.

La respuesta incluye siempre `decision: SIGNALS_ONLY`, `creates_moment: false` y `creates_clip: false`. No se crean momentos ni clips por encontrar palabras. La duración de ventana se expone como contexto; la evaluación de pausas, preguntas/respuestas, cierre y calidad del contexto sigue pendiente de la fase del detector completo. El extractor ya entrega objetos de señales para ese evaluador futuro sin depender de un idioma o proveedor de IA.

## Importar y exportar

**Exportar** descarga `liveclip_rules.json`: versión del esquema, grupos, reglas, perfiles y referencia al perfil activo. **Importar** abre una confirmación y valida el archivo completo antes de guardar en una única transacción.

La importación **agrega copias**, asigna IDs nuevos y remapea sus relaciones; no sobrescribe reglas existentes. Se conserva el perfil activo de la instalación receptora. Las reglas importadas y habilitadas pueden entrar en vigor inmediatamente si el perfil actual las admite. Importar dos veces crea dos conjuntos independientes.

El formulario acepta archivos de hasta 1 MB; el esquema admite hasta 1.000 reglas, 100 grupos y 100 perfiles por archivo. Patrones: hasta 500 caracteres. Nombres y categorías: hasta 100. Se rechazan versiones desconocidas, campos desconocidos, referencias rotas, IDs duplicados y pesos fuera de rango o no finitos. Un error no deja una importación parcial.

## Arquitectura y persistencia

```text
SQLite → RulesRepository → RulesCache (snapshot inmutable)
                                      ↓
Ventana de transcripción → FeatureExtractor → HeuristicEvaluator → señales
```

`backend/app/detection/` separa modelos, esquemas, repositorio, caché, extractor, integración de transcripción y API. Las mutaciones se serializan con un lock; después de confirmar la transacción se publica una instantánea completa de reglas efectivas. La extracción no consulta SQLite por palabra ni por regla. Una revisión numérica permite actualizar UI y evaluación. La interfaz vuelve a consultar la configuración al guardar y periódicamente para sincronizar otras pestañas.

Se agregan las tablas `moment_detection_rules`, `moment_rule_groups`, `moment_detection_profiles` y `moment_detection_state`. No se modifican las tablas ni archivos de clips existentes. Se mantiene la restricción actual a un único worker de backend.

API:

```text
GET/POST       /moment-rules
PUT/DELETE     /moment-rules/{id}
POST           /moment-rules/{id}/enable
POST           /moment-rules/{id}/disable
GET/POST       /moment-rules/groups
PUT/DELETE     /moment-rules/groups/{id}
GET/POST       /moment-profiles
PUT/DELETE     /moment-profiles/{id}
POST           /moment-profiles/active       { "profile_id": "..." | null }
GET            /moment-rules/configuration
GET            /moment-rules/export
POST           /moment-rules/import
POST           /moment-rules/preview         { "text": "...", "language": "..." }
```

`/ws/live` incorpora `detection` con las señales de la ventana actual. Los errores al recibir señales no interrumpen el guardado de transcripción.

## Verificación

`backend/tests/test_detection_rules.py` prueba CRUD, cambios sin reinicio, modos de coincidencia, mayúsculas, Unicode, idiomas, pesos, perfiles, grupos, persistencia, importación/exportación, validación, ausencia de consultas SQL durante la extracción y actualización de ventanas sin audio nuevo. Se comprobó también en la interfaz la creación de reglas, el laboratorio y la selección de perfiles en Live Monitor.
