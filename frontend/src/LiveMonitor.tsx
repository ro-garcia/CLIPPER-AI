import { Clapperboard, Radio, Square, Video } from "lucide-react";
import { api, time } from "./api";
import { Badge, TranscriptPanel } from "./components";
import { useStudio } from "./useStudio";
import { ProfileSelector } from "./detection/ProfileSelector";
import { SignalPanel } from "./detection/SignalPanel";
import { AIOverview } from './ai/MomentsPage';
import { ClipTimingSettings } from './ClipTimingSettings';

export function LiveMonitor({
  studio,
  connectPanel,
  busy,
  action,
  create,
  notify,
}: {
  studio: ReturnType<typeof useStudio>;
  connectPanel: React.ReactNode;
  busy: string;
  action: (name: string, work: () => Promise<void>) => Promise<void>;
  create: () => Promise<void>;
  notify: (message: string) => void;
}) {
  const { stream, clips, transcripts, system, resources, connected } = studio;
  const active = ["starting", "live", "stopping"].includes(stream.state),
    ready = clips.filter((c) => c.status === "ready");
  return (
    <>
      {studio.streams.filter(s => ['starting', 'live', 'stopping'].includes(s.state)).length < 2 && connectPanel}
      <div className="stream-selector" aria-label="Transmisiones">
        {studio.streams.map((source, index) => (
          <button key={source.stream_id || index}
            className={stream.stream_id === source.stream_id ? 'primary' : 'secondary'}
            aria-pressed={stream.stream_id === source.stream_id}
            onClick={() => studio.selectStream(source.stream_id)}>
            <Radio size={16} /> Fuente {index + 1}: {source.info?.title || 'Conectando…'}
            <span>{source.state === 'live' ? ' · Grabando' : ` · ${source.state}`}</span>
          </button>
        ))}
      </div>
      <ProfileSelector />
      <AIOverview studio={studio} liveOnly/>
      <div className="monitor-grid">
        <section className="panel monitor">
          <div className="panel-heading">
            <h3>
              <Video size={17} /> {stream.info?.title || "Monitor de fuente"}
            </h3>
            <Badge tone={active ? "red" : "muted"}>
              {connected ? stream.state.toUpperCase() : 'SIN CONEXIÓN'}
            </Badge>
          </div>
            <div className="monitor-empty recording-status" role="status">
              <div className="monitor-gridlines" />
              <Radio size={42} />
              <h3>
                {!connected ? "Sin conexión con el backend" : stream.state === "live" ? "Grabando transmisión" : stream.state === "stopping" ? "Deteniendo captura…" : stream.state === "starting"
                  ? "Conectando tu transmisión…"
                  : "Tu próxima historia empieza en directo"}
              </h3>
              <p>
                {!connected ? "No se puede confirmar el estado actual de la grabación. Intentando reconectar…" : stream.state === "live" ? "El buffer se guarda en tu equipo. Puedes crear clips mientras continúa la grabación." : stream.state === "starting"
                  ? "Esperando los primeros segmentos de video."
                  : "Analiza una fuente para activar el monitor."}
              </p>
              <span>CAPTURA LOCAL · SIN REPRODUCCIÓN DE VIDEO</span>
            </div>
          <div className="monitor-transport">
            <div>
              <span className={`dot ${stream.state === "live" ? "red" : ""}`} />
              <strong>{time(stream.elapsed)}</strong>
              <small>
                {stream.info?.height ? `${stream.info.height}p` : "—"} ·{" "}
                {stream.info?.fps ? `${stream.info.fps} FPS` : "FPS —"}
              </small>
            </div>
            <div>
              <button
                className="primary"
                disabled={
                  stream.state !== "live" ||
                  stream.buffer_seconds < studio.clipTiming.before_seconds ||
                  !connected ||
                  !!busy
                }
                onClick={() => void create()}
              >
                <Clapperboard size={16} /> Crear clip
              </button>
              <button
                className="stop-button"
                disabled={!active || !connected || !!busy}
                onClick={() =>
                  void action("stop", async () => {
                    await api(`/streams/stop?stream_id=${encodeURIComponent(stream.stream_id || '')}`, {});
                    notify("Captura detenida.");
                  })
                }
                title="Detener transmisión"
              >
                <Square size={15} />
              </button>
            </div>
          </div>
          <div className="buffer-track">
            <div>
              <span>BUFFER CIRCULAR</span>
              <small>
                {time(stream.buffer_seconds).slice(3)} /{" "}
                {time(stream.buffer_capacity).slice(3)}
              </small>
            </div>
            <progress
              max={stream.buffer_capacity}
              value={stream.buffer_seconds}
            />
            <p>Crear clip conserva {studio.clipTiming.before_seconds} segundos anteriores + {studio.clipTiming.after_seconds} posteriores ({studio.clipTiming.before_seconds + studio.clipTiming.after_seconds} s en total).</p>
            <details><summary>Configurar duración de clips</summary><ClipTimingSettings studio={studio}/></details>
          </div>
        </section>
        <TranscriptPanel
          items={transcripts}
          status={stream.transcription_status}
        />
      </div>
      <SignalPanel evaluation={studio.detection} />
      {!!stream.dropped_segments && <div className="notice">Se omitieron {stream.dropped_segments} segmentos de transcripción para limitar la carga. El video sigue en el buffer; la detección automática puede omitir momentos.</div>}
    </>
  );
}
