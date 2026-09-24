# Subtítulos y render vertical

Las fases 4 y 5 convierten un clip creado desde un Candidate Moment en un MP4 vertical local. Reutilizan la transcripción de Whisper que ya pertenece al stream: no ejecutan Whisper ni envían datos fuera del equipo.

## Uso

1. En **Moments**, crea un clip de un candidato cuyo preview indique `READY`.
2. Abre **Clips** y selecciona ese clip.
3. Pulsa **Generar formato vertical**. La cola procesa un render a la vez y puedes cerrar el diálogo o seguir usando el estudio.
4. El estado muestra las etapas de preparación, subtítulos, video, codificación y finalización. Cuando diga `READY`, el diálogo permite comparar el original con la versión 9:16, descargar el MP4 y los archivos SRT/ASS.

La configuración está en **Settings → Subtítulos y formato**. Puedes elegir resolución, CRF, FPS, recorte central, fondo desenfocado o negro, área segura, estilo, tipografía, posición y límites de lectura de los subtítulos. `Smart crop` y `Seguimiento` usan por ahora el recorte central como fallback local, sin bloquear la exportación.

El resultado se guarda junto al clip, sin modificar `original.mp4`:

```text
backend/storage/clips/<clip-id>/
  original.mp4
  subtitles.srt
  subtitles.ass
  vertical.mp4
```

Un clip anterior que no fue creado desde un Candidate Moment puede no tener rango de transcripción. En ese caso la interfaz mostrará el motivo y podrás crear un clip nuevo desde Moments. Si falta espacio, el video original, o FFmpeg no puede renderizar, el trabajo pasa a `FAILED` y puede regenerarse.
