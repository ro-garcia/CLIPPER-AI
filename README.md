# LiveClip AI — fase 1

Estudio local para Windows: URL → FFmpeg → buffer circular → faster-whisper → clip manual MP4. React, TypeScript, Vite, Tailwind, Lucide, FastAPI y SQLite/SQLAlchemy. No requiere una API de IA ni envía audio a un proveedor de transcripción.

Nuevo: **Settings → Moment Detection** permite administrar reglas, grupos y perfiles sin reiniciar, importar/exportar JSON y probar señales lingüísticas. El selector de perfil también está en Live Monitor. Consulta [la guía del diccionario](docs/detection-rules.md). Esto prepara el detector; todavía no genera momentos ni clips automáticamente.

## Abrir el estudio

Con las dependencias instaladas, ejecuta **LiveClip.cmd** o abre <http://127.0.0.1:5173> si los servicios ya están encendidos. El lanzador inicia frontend y backend en segundo plano. Esta es la versión de desarrollo local, todavía no un instalador de escritorio.

1. Pega una URL HTTP/HTTPS y pulsa **Analizar enlace**.
2. Revisa la fuente y pulsa **Iniciar monitoreo**.
3. Espera al menos 30 segundos de buffer. El monitor muestra **Grabando transmisión**, el tiempo y el buffer, sin reproducir video. Puedes agregar una segunda fuente y elegirla con los botones de fuente.
4. **Crear clip** conserva los 30 segundos anteriores y espera 15 posteriores. El punto de referencia es el tiempo de medios reportado por FFmpeg al pulsar el botón, con la latencia propia de la fuente.
5. El clip pasa por `capturing → processing → ready`. Ábrelo en **Clips** para reproducirlo o exportarlo.
6. Usa **Detener transmisión** para cerrar solo la fuente seleccionada; la otra continúa grabando. Si faltan los segundos posteriores de un clip, se marca como error y se eliminan sus segmentos temporales.

Cerrar la pestaña no detiene el backend. Detén la captura antes de cerrar el estudio. Los scripts de desarrollo permiten detener cada servicio con Ctrl+C cuando se ejecutan en terminal.

Para apagar los servicios iniciados con el lanzador, haz doble clic en **Stop-LiveClip.cmd**. Detiene la transmisión y cierra los servidores del proyecto. Espera a que tus clips terminen de procesarse antes de usarlo. Después puedes cerrar la pestaña del navegador.

## Xubuntu

Desde una terminal en la raíz del proyecto, habilita los scripts una vez y prepara el equipo. El primer comando instala Python, FFmpeg con libass, fuentes, Node.js y las dependencias del proyecto; `--with-ollama` agrega Ollama local para probar también la detección y el scoring.

```bash
chmod +x Prepare-Xubuntu.sh Start-LiveClip-Xubuntu.sh Stop-LiveClip-Xubuntu.sh
./Prepare-Xubuntu.sh
# Opcional para fases 2 y 3: ./Prepare-Xubuntu.sh --with-ollama
./Start-LiveClip-Xubuntu.sh --open
```

El estudio queda ligado a `127.0.0.1:5173`. Para apagarlo, usa:

```bash
./Stop-LiveClip-Xubuntu.sh
```

Para comprobar solamente subtítulos y formato vertical sin iniciar una transmisión ni Ollama:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_rendering.py -q
```

## Entorno verificado

Windows; Python 3.13.7; Node 24.21.0; npm 11.19.0; Git 2.51.0. CPU Intel i7-6700HQ, RAM 31,9 GiB, GPU NVIDIA GTX 1060 con 6 GiB de VRAM. FFmpeg se instaló mediante `imageio-ffmpeg` dentro del entorno Python, sin modificar el PATH global.

Configuración inicial: Whisper **base**, CPU, INT8, dos hilos compartidos por ambas fuentes; captura por copia directa, sin recodificación continua. Los clips y renders se procesan de uno en uno con FFmpeg y dos hilos de codificación. El modelo base está descargado en `backend/storage/models`. La aceleración CUDA no está validada: que el driver muestre una versión CUDA no demuestra que estén instaladas las bibliotecas requeridas por CTranslate2.

Se observaron aproximadamente 2,9 GiB libres en disco. La captura exige al menos 512 MiB para iniciar y se detiene si quedan menos de 256 MiB. Los clips exportados sí se conservan; revisa su espacio periódicamente.

## Instalación reproducible

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
cd frontend
npm.cmd ci
```

El archivo `requirements.txt` define dependencias directas y `requirements-lock.txt` registra las versiones verificadas en Windows/Python 3.13. El primer uso de un modelo nuevo necesita Internet para descargarlo. Después, la transcripción utiliza los pesos locales.

Para desarrollo, dos terminales:

```powershell
./scripts/start-backend.ps1
```

```powershell
./scripts/start-frontend.ps1
```

Frontend: <http://127.0.0.1:5173>. Backend: <http://127.0.0.1:8000>. API interactiva: <http://127.0.0.1:8000/docs>.

## Configuración

Copia `.env.example` a `.env` en la raíz y reinicia el backend:

| Variable | Valor inicial | Uso |
| --- | --- | --- |
| `BUFFER_MINUTES` | `10` | Retención, de 1 a 30 minutos |
| `WHISPER_MODEL` | `base` | Modelo; `tiny` reduce el consumo |
| `WHISPER_DEVICE` | `cpu` | Dispositivo; CUDA queda por validar |
| `WHISPER_THREADS` | `2` | Hilos del único motor compartido, de 1 a 8 |
| `CAPTURE_MODE` | `copy` | Copia directa; `encode` permite recodificar fuentes incompatibles con MPEG-TS |
| `CAPTURE_MAX_HEIGHT` | `720` | Calidad preferida al resolver la fuente; en copia directa no redimensiona y puede usar la calidad disponible |
| `STORAGE_DIR` | `backend/storage` | Ruta absoluta opcional para todo el almacenamiento |
| `FFMPEG_PATH` | detección automática | Ruta absoluta opcional a FFmpeg |

La página Settings muestra la configuración real, pero aún no la edita. No hay opciones aparentes que activen funciones de futuras fases.

## Arquitectura

```text
backend/app/
  main.py                 REST, WebSocket, archivos y ciclo de vida
  config.py               Configuración y resolución de FFmpeg
  database.py             Modelos SQLAlchemy, SQLite WAL
  services/
    media.py              Validación de URL, yt-dlp y FFmpeg sin shell
    stream.py             Captura, supervisión y coordinación
    buffer.py             Índice de segmentos terminados y retención
    transcription.py      Cola limitada, extracción mono 16 kHz y Whisper
    clips.py              Copias temporales, codificación y estados
frontend/src/
  App.tsx                 Navegación y composición del estudio
  AppSidebar.tsx          Navegación colapsable
  Dashboard.tsx           Resumen de sesión y clips recientes
  SourcePanel.tsx         Análisis y conexión de fuentes
  LiveMonitor.tsx         Indicador de grabación, selector de fuente y transcripción
  SettingsPage.tsx        Estado del sistema
  components.tsx          Componentes reutilizables
  useStudio.ts            WebSocket con reconexión y recursos del sistema
```

Hasta dos capturas tienen sus propios procesos FFmpeg, buffers, logs y clips. La copia directa evita recodificar todo el directo. Los segmentos se cierran en cuadros clave de la fuente, por lo que pueden superar cinco segundos y variar la latencia. Si una fuente no permite copiar sus códecs a MPEG-TS, configura `CAPTURE_MODE=encode` y reinicia. La calidad preferida es 720p cuando la plataforma la ofrece.

Ambas fuentes comparten un único modelo Whisper y una cola de doce segmentos como máximo, con hasta seis pendientes por fuente. Si no alcanza el ritmo, se omite transcripción y el monitor indica cuántos segmentos se omitieron; el video sigue grabándose, pero la detección automática puede perder momentos. FFmpeg procesa un solo trabajo auxiliar a la vez (clips, previews de momentos, extracción de audio o render), con hilos limitados. Hasta tres clips manuales pueden estar pendientes entre las dos fuentes.

El buffer conserva el límite configurado más el margen de los cuadros clave. Cada fuente tiene su propia retención. Al liberar una sesión terminada se elimina su buffer; los clips terminados permanecen. Al reiniciar el backend se limpian buffers y audio temporales y se marcan como fallidos los clips interrumpidos. La base de datos conserva streams, transcripciones y clips.

El navegador no carga ni reproduce el directo. Solo reproduce clips al pulsar sus controles. El WebSocket actualiza el estado cada tres segundos; los recursos del equipo se consultan cada ocho segundos. La captura sigue activa si se cierra la pestaña. `POST /streams/stop` detiene todas las fuentes para conservar compatibilidad con el apagado; `?stream_id=...` detiene solo una. `POST /clips/create?stream_id=...` crea un clip de la fuente indicada; con dos activas es obligatorio especificarla. `/streams/active` devuelve las sesiones y sus estados.

Estos límites reducen la concurrencia y el consumo; no constituyen un tope absoluto de CPU o RAM del sistema. La carga de Ollama, la calidad/bitrate de las fuentes y otros programas también influyen. La captura conserva la protección por espacio libre en disco.

## Pruebas realizadas

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q
cd ../frontend
npm.cmd run build
npm.cmd run lint
```

La suite automatizada cubre captura y clips, reglas y perfiles, detección de candidatos y evaluación IA: contexto, scores, fórmula, historial, concurrencia, reintentos y errores. Ver [guía de IA](docs/ai-scoring.md).

`backend/tests/integration_local.py` ejecuta una prueba multimedia real contra el backend encendido. Requiere el audio `backend/storage/test-speech.flac`, obtenido de la [muestra pública de Whisper](https://github.com/openai/whisper/blob/main/tests/jfk.flac). Genera 75 segundos de video de prueba con voz y lo sirve por HTTP en el puerto local 8877. Comprueba análisis, captura, buffer, playlist HLS, transcripción, MP4 con audio/video de 45 segundos y reproducción HTTP Range. La prueba deja un clip identificado como `test-source` en la galería. Se ejecutó correctamente, también tras ajustar el anclaje temporal del botón.

Se verificó visualmente el monitor y se reprodujo un MP4 desde la galería en el navegador. Las barras de color y la voz de los clips `test-source` son material de prueba generado, no contenido de una transmisión del usuario.

## Límites de esta fase

- Se ha probado captura real de Kick. La compatibilidad depende de yt-dlp y de que la fuente entregue audio y video accesibles sin DRM ni eludir controles. No se usan cookies ni credenciales del navegador.
- FFmpeg intenta reconexión HTTP; una fuente expirada o una desconexión definitiva requiere iniciar de nuevo. No hay restauración de sesiones entre reinicios.
- Hasta dos streams activos y tres clips manuales pendientes en total. La codificación auxiliar se ejecuta de una en una. Los fragmentos de voz pueden cortar frases y su transcripción tiene latencia variable según hardware.
- Detección de candidatos y scoring local con Ollama están integrados. La IA está desactivada inicialmente y, al activarla, empieza en modo manual; la creación de clips continúa siendo manual. Configuración y uso en [Settings → AI](docs/ai-scoring.md). Los metadatos sociales y la publicación siguen pendientes.
- Los clips creados desde Moments pueden procesarse localmente con subtítulos SRT/ASS y una salida vertical 9:16 de FFmpeg. Consulta [la guía de render final](docs/final-rendering.md). La publicación y las redes sociales siguen pendientes.
- No se ha empaquetado con Tauri/Electron. El backend debe ejecutarse con un solo worker y ligado a loopback; no es un servicio para exponer en Internet.

Logs: `backend/storage/logs/app.log` (rotativo) y `capture-<stream_id>.log` (por captura). Ante errores, el frontend muestra el estado y los logs permiten diagnosticar la causa. Las URLs se pasan como argumentos, sin shell; nombres de archivos generados mediante UUID y acceso a clips verificado por base de datos. Se restringen Host y Origin a la aplicación local.

Referencias técnicas: [segmentación FFmpeg](https://ffmpeg.org/ffmpeg-formats.html#segment_002c-stream_005fsegment_002c-ssegment), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

La prueba `tests/test_dual_capture.py` usa dos fuentes HTTP sintéticas y FFmpeg real: verifica buffers independientes, clips de 45 segundos con audio, identidad visual de cada fuente y parada independiente. No requiere plataformas externas ni descargar Whisper. `tests/test_multistream.py` comprueba admisión concurrente, aislamiento de señales, cola compartida y exclusión de trabajos FFmpeg.

## Duración de clips manuales

Configura **Settings → Duración de clips**, o **Live Monitor → Configurar duración de clips**. Elige segundos anteriores al clic (mínimo 1, hasta la capacidad del buffer) y posteriores (pueden ser 0). La suma admite hasta 300 segundos para limitar el procesamiento. El valor inicial sigue siendo 30 + 15 = 45 segundos.

**Guardar duración** conserva el ajuste en SQLite para ambas fuentes, sin reiniciar. Solo cambia los clips nuevos; los que ya se están capturando conservan sus tiempos. El botón Crear clip se habilita al reunir el buffer necesario. Con 0 segundos posteriores aún se espera a que cierre el segmento que contiene el clic. Los clips de Moments conservan la duración del momento detectado.
