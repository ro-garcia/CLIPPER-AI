import {
  Activity,
  ArrowRight,
  AudioLines,
  Check,
  Clapperboard,
  Clock3,
  Database,
  Radio,
} from "lucide-react";
import { api, time } from "./api";
import { Badge, Empty, Metric } from "./components";
import { useStudio } from "./useStudio";

export function Dashboard({
  studio,
  connectPanel,
  gallery,
  setPage,
}: {
  studio: ReturnType<typeof useStudio>;
  connectPanel: React.ReactNode;
  gallery: (limit?: number) => React.ReactNode;
  setPage: (page: string) => void;
}) {
  const { stream, clips, transcripts, system, resources, connected } = studio;
  const active = ["starting", "live", "stopping"].includes(stream.state),
    ready = clips.filter((c) => c.status === "ready");
  return (
    <>
      <div className="metrics">
        <Metric
          label="FUENTES ACTIVAS"
          value={`${studio.streams.filter(source => ['starting', 'live', 'stopping'].includes(source.state)).length} / 2`}
          detail={
            active
              ? stream.info?.platform || "Conectando"
              : "Listo para conectar una fuente"
          }
          icon={<Radio size={17} />}
        />
        <Metric
          label="TIEMPO MONITOREADO"
          value={time(stream.elapsed)}
          detail="Sesión actual"
          icon={<Clock3 size={17} />}
        />
        <Metric
          label="CLIPS CREADOS"
          value={String(ready.length).padStart(2, "0")}
          detail={`${clips.filter((c) => ["capturing", "processing"].includes(c.status)).length} en proceso · guardados localmente`}
          icon={<Clapperboard size={17} />}
        />
        <Metric
          label="BUFFER CIRCULAR"
          value={time(stream.buffer_seconds).slice(3)}
          detail={`de ${time(stream.buffer_capacity).slice(3)} min · limpieza automática`}
          icon={<Database size={17} />}
        />
      </div>
      {!active ? (
        connectPanel
      ) : (
        <section className="source-panel current-stream">
          <div>
            <Badge tone="red">{stream.state.toUpperCase()}</Badge>
            <h2>{stream.info?.title}</h2>
            <p>
              {time(stream.elapsed)} de monitoreo · {transcripts.length}{" "}
              segmentos transcritos
            </p>
          </div>
          <button className="primary" onClick={() => setPage("Live Monitor")}>
            Abrir Live Monitor <ArrowRight size={16} />
          </button>
        </section>
      )}
      <div className="dashboard-lower">
        <section className="panel">
          <div className="panel-heading">
            <h3>
              <Clapperboard size={17} /> Clips recientes
            </h3>
            <button className="text-button" onClick={() => setPage("Clips")}>
              Ver todos <ArrowRight size={14} />
            </button>
          </div>
          {clips.length ? (
            gallery(3)
          ) : (
            <Empty
              icon={<Clapperboard size={27} />}
              title="Los grandes momentos vienen en camino"
              description="Inicia un monitoreo y crea tu primer clip. Aparecerá aquí, listo para reproducir."
            />
          )}
        </section>
        <section className="panel session-panel">
          <div className="panel-heading">
            <h3>
              <Activity size={17} /> Sesión del estudio
            </h3>
            <span className="dot green" />
          </div>
          <div className="activity-item">
            <div className="activity-icon">
              <Check size={15} />
            </div>
            <div>
              <strong>
                {connected ? "Backend conectado" : "Esperando backend"}
              </strong>
              <p>
                {connected
                  ? "Tu estudio está disponible localmente."
                  : "Inicia el backend para conectar el estudio."}
              </p>
              <small>LOCALHOST · 8000</small>
            </div>
          </div>
          <div className="activity-item">
            <div className="activity-icon purple">
              <AudioLines size={15} />
            </div>
            <div>
              <strong>Motor de transcripción</strong>
              <p>
                {stream.transcription_status === "ready"
                  ? "Modelo cargado y listo."
                  : stream.transcription_status === "loading"
                    ? "Descargando o cargando el modelo…"
                    : "El modelo se carga con el primer audio."}
              </p>
              <small>
                WHISPER {system?.model?.toUpperCase() || "BASE"} · CPU INT8
              </small>
            </div>
          </div>
          <div className="workflow-note">
            <span>EL FLUJO DE TU ESTUDIO</span>
            <div>
              <Radio />
              <i />
              <AudioLines />
              <i />
              <Clapperboard />
            </div>
            <p>Conecta. Transcribe. Captura.</p>
          </div>
        </section>
      </div>
    </>
  );
}
