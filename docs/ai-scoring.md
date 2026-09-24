# Evaluación inteligente de momentos con Ollama local

La fase 3 puntúa los candidatos que ya detectan las reglas de las fases 1 y 2. No cambia las reglas, no sustituye Whisper y no crea clips por sí sola. Todo el análisis se ejecuta en tu equipo con Ollama; las transcripciones no se envían a servicios externos.

## Prueba funcional

1. Inicia Ollama y confirma que tienes un modelo instalado, por ejemplo `gemma4:26b`.
2. Abre **Settings → AI**. Selecciona **Ollama · Local**, elige el modelo y pulsa **Probar conexión**. La prueba consulta solamente el servicio local y sus modelos instalados.
3. Activa **Evaluación con IA** y guarda. Elige el modo **Manual** para decidir uno por uno qué candidatos analizar.
4. Inicia una transmisión y espera a que las reglas creen candidatos en **Moments**. Un candidato no es un clip: conserva un preview temporal y su transcripción.
5. En **Moments**, pulsa **Evaluar** en un candidato que tenga preview o transcripción. Se pondrá en una cola de una sola evaluación y pasará por `QUEUED`, `EVALUATING` y `EVALUATED`.
6. Abre **Detalles** para ver el contexto utilizado, la versión del prompt, modelo, latencia, tokens, resumen y motivo. Crea el clip solamente con el botón manual **Crear clip** si quieres conservarlo.

Con modo **Automático**, cada nuevo candidato válido entra en la misma cola al detectarse. El modo controla únicamente la solicitud de evaluación. Aunque una puntuación sea alta, la aplicación nunca crea un clip automáticamente en esta fase.

Si usas un modelo grande, deja un tiempo límite suficiente. `gemma4:26b` puede tardar varios minutos en la primera respuesta. La aplicación no descarga modelos: el nombre debe corresponder a uno que ya aparezca en Ollama.

## Cómo se calcula la nota

La confianza de detección y la puntuación de IA son medidas distintas.

- **Confianza de detección** (0–100 %) procede de tus reglas, duración y estructura de la ventana. Una coincidencia de palabra con peso `0.10` añade una señal; no significa “10 % de calidad” ni crea un clip.
- **Puntuación IA** (0–10) evalúa el texto completo del candidato. El modelo devuelve nueve criterios validados y el backend calcula el total. El modelo no puede definir la nota total, el nivel ni la acción recomendada.

| Criterio | Significado |
| --- | --- |
| Interés | Qué tan atractivo resulta el contenido. |
| Claridad | Si se entiende sin ambigüedad. |
| Viralidad | Potencial de que alguien quiera compartirlo, sin predecir vistas. |
| Independencia | Si funciona como pieza aislada. |
| Gancho | Fuerza del inicio. |
| Cierre | Si termina con una idea completa. |
| Valor informativo | Utilidad, novedad o aprendizaje que aporta. |
| Dependencia de contexto | Cuánto necesita material anterior para entenderse; se muestra como diagnóstico. |
| Completitud | Si plantea y cierra una unidad de contenido; se muestra como diagnóstico. |

La fórmula predeterminada es:

`interés × 0.25 + claridad × 0.20 + viralidad × 0.20 + independencia × 0.15 + gancho × 0.10 + cierre × 0.05 + valor informativo × 0.05`

Los siete pesos editables deben sumar exactamente 1.0. Dependencia de contexto y completitud no inflan la nota: ayudan a interpretar por qué un momento puede necesitar revisión.

El nivel se calcula en el backend con los umbrales de Settings:

- **HIGH_POTENTIAL**: desde 8.5.
- **GOOD**: desde 7.0.
- **MEDIUM**: desde 5.0.
- **LOW**: por debajo de 5.0.

La recomendación también la calcula el backend: **CREATE_CLIP** desde 8.5, **REVIEW** desde 7.0 y **DISCARD** por debajo. Es una guía visible; no ejecuta ninguna acción sobre el video.

## Contexto, cola y conservación de datos

- Se conserva el fragmento candidato completo. El contexto anterior y posterior se ajusta al presupuesto configurado sin recortar el candidato.
- Durante un directo, la evaluación espera de forma acotada al contexto posterior. Whisper sigue funcionando en su propia cola.
- El límite inicial es 20 s anteriores, hasta 45 s si hace falta completar una idea, 10 s posteriores y 12 000 caracteres totales. Si el candidato por sí solo supera el límite, la evaluación falla de forma explícita y puede volver a intentarse con un límite mayor.
- La cola acepta hasta 100 solicitudes y procesa exactamente una a la vez. Cada stream tiene un límite configurable de 100 evaluaciones.
- Errores de Ollama, tiempos límite o JSON inválido no detienen la captura, Whisper ni la creación manual de clips. Se realizan los reintentos configurados y queda el motivo para reevaluar.
- Se conserva el historial de evaluaciones. Una evaluación idéntica reutiliza el resultado por huella de transcripción, proveedor, modelo, prompt y ajustes; **Reevaluar** fuerza una nueva pasada y conserva la anterior.
- Los previews son temporales. La transcripción, candidato, configuraciones y evaluaciones permanecen aunque ya no exista el video temporal. Los clips que creas manualmente permanecen en la galería.

## Datos que recibe Ollama

El prompt identifica explícitamente tres bloques: contexto anterior, momento candidato y contexto posterior. El contexto sirve para entender referencias, pero la evaluación se centra en el candidato. Las transcripciones se tratan como datos no confiables: cualquier instrucción incluida en ellas se ignora. El proveedor debe responder un JSON estructurado que se valida antes de guardarse.

Los prompts viven en `backend/app/ai/prompts/moment_evaluator.py` y actualmente usan la versión `v2`.

## Estado, API y validación

Estados posibles: ausencia de evaluación, `QUEUED`, `EVALUATING`, `RETRYING`, `EVALUATED` y `FAILED`. Desactivar la IA impide nuevas evaluaciones y deja intactos candidatos, clips e historial.

Las rutas relevantes son `/ai/settings`, `/ai/settings/test`, `/ai/status`, `/ai/models`, `/ai/statistics`, `/ai/ranking`, `/moments/{id}/evaluate`, `/moments/{id}/reevaluate`, `/moments/{id}/evaluations` y `/ai/evaluate-batch`.

Para verificar la implementación sin tocar datos de producción:

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q
cd ../frontend
npm.cmd run build
```

La comprobación manual local está en `backend/tests/manual_ollama_check.py`. Usa una base temporal y Ollama local, sin escribir en la base de datos del estudio. No forma parte de pytest porque invoca el modelo real.

La fase 3 no incluye subtítulos, reencuadre vertical, seguimiento de rostros, publicación ni automatización de clips.
