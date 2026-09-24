import { SourcePanel } from "./SourcePanel";
import { AppSidebar, navigation } from "./AppSidebar";
import { Dashboard } from "./Dashboard";
import { LiveMonitor } from "./LiveMonitor";
import { SettingsPage } from "./SettingsPage";
import { MomentsPage } from './ai/MomentsPage';
import { PublishingPage } from './publishing/PublishingPage';
import { useState, useEffect, useRef } from "react";
import {
  ArrowRight,
  Cpu,
  Database,
  FolderOpen,
  HardDrive,
  Plus,
  Radio,
  Settings,
  Sparkles,
} from "lucide-react";
import { api, time } from "./api";
import { Badge, ClipCard, ClipModal, Empty } from "./components";
import { useStudio } from "./useStudio";
import type { Clip } from "./types";

export default function App() {
  const studio = useStudio(),
    { stream, clips, transcripts, system, resources, connected } = studio;
  const [page, setPage] = useState("Dashboard"),
    [collapsed, setCollapsed] = useState(false),
    [busy, setBusy] = useState(""),
    [toast, setToast] = useState(""),
    [selected, setSelected] = useState<Clip | null>(null);
  const active = studio.streams.some(source => ["starting", "live", "stopping"].includes(source.state)),
    ready = clips.filter((c) => c.status === "ready"),
    phase = navigation.find((n) => n.name === page)?.phase;
  async function action(name: string, work: () => Promise<void>) {
    setBusy(name);
    try {
      await work();
    } catch (error) {
      setToast(error instanceof Error ? error.message : "Ocurrió un error");
    } finally {
      setBusy("");
    }
  }
  const notify = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(""), 6000);
  };
  const previousClips = useRef<Record<string, string>>({});
  useEffect(() => {
    for (const clip of clips) {
      const previous = previousClips.current[clip.id];
      if (previous && previous !== clip.status) {
        if (clip.status === "ready")
          notify("Clip generado. Ya puedes reproducirlo y exportarlo.");
        if (clip.status === "error")
          notify(clip.error || "No se pudo generar el clip.");
      }
    }
    previousClips.current = Object.fromEntries(
      clips.map((clip) => [clip.id, clip.status]),
    );
  }, [clips]);
  const create = () =>
    action("clip", async () => {
      const clip = await api<Clip>(`/clips/create?stream_id=${encodeURIComponent(stream.stream_id || '')}`, {});
      setSelected(clip);
      notify(`Preparando un clip de ${clip.duration} segundos.`);
    });
  const connectPanel = (
    <SourcePanel
      active={studio.streams.filter(s => ['starting', 'live', 'stopping'].includes(s.state)).length >= 2}
      onStarted={(streamId) => { studio.selectStream(streamId); setPage("Live Monitor"); }}
      notify={notify}
    />
  );
  const gallery = (limit?: number) => (
    <div className="clip-grid">
      {(limit ? clips.slice(0, limit) : clips).map((clip) => (
        <ClipCard key={clip.id} clip={clip} onClick={() => setSelected(clip)} />
      ))}
    </div>
  );
  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <AppSidebar
        page={page}
        setPage={setPage}
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        clips={clips}
        active={active}
      />
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>
            <strong>{page}</strong>
          </div>
          <div className="system-lights">
            <span>
              <i className={`dot ${system ? "green" : ""}`} /> Backend
            </span>
            <span>
              <i
                className={`dot ${system?.ffmpeg === "installed" ? "green" : ""}`}
              />{" "}
              FFmpeg
            </span>
            <span>
              <i
                className={`dot ${stream.transcription_status === "ready" ? "green" : "amber"}`}
              />{" "}
              Whisper
            </span>
            <span className="top-divider" />
            <Badge
              tone={
                !connected
                  ? "red"
                  : stream.transcription_status === "error"
                    ? "amber"
                    : "green"
              }
            >
              {!connected
                ? "BACKEND OFFLINE"
                : stream.transcription_status === "error"
                  ? "SYSTEM DEGRADED"
                  : "STUDIO ONLINE"}
            </Badge>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                LIVECLIP /{" "}
                {page === "Dashboard" ? "OVERVIEW" : page.toUpperCase()}
              </span>
              <h1>
                {page === "Dashboard"
                  ? "Tu estudio, en tiempo real."
                  : page === "Live Monitor"
                    ? "Live Monitor"
                    : page === "Clips"
                      ? "Cada gran momento, a mano."
                      : page === "Library"
                        ? "Biblioteca local"
                        : page === "Settings"
                          ? "Configuración del estudio"
                          : page}
              </h1>
              <p>
                {page === "Dashboard"
                  ? "Del directo al clip. Sin salir de tu equipo."
                  : page === "Live Monitor"
                    ? "Hasta dos fuentes grabando. Selecciona una para crear clips."
                    : page === "Clips"
                      ? "Tus clips originales, listos para revisar y exportar."
                      : page === "Settings"
                        ? "Estado real del equipo y configuración de esta fase."
                        : "Tu espacio de producción audiovisual."}
              </p>
            </div>
            {!phase && page !== "Settings" && (
              <button
                className="secondary"
                onClick={() => {
                  setPage("Live Monitor");
                  document
                    .querySelector<HTMLInputElement>(".url-input input")
                    ?.focus();
                }}
              >
                <Plus size={16} /> Nueva fuente
              </button>
            )}
          </div>
          {stream.error && <div className="notice error">{stream.error}</div>}
          {stream.transcription_error && (
            <div className="notice">
              Transcripción: {stream.transcription_error}
            </div>
          )}
          {page === "Dashboard" && (
            <Dashboard
              studio={studio}
              connectPanel={connectPanel}
              gallery={gallery}
              setPage={setPage}
            />
          )}
          {page === "Live Monitor" && (
            <LiveMonitor
              studio={studio}
              connectPanel={connectPanel}
              busy={busy}
              action={action}
              create={create}
              notify={notify}
            />
          )}
          {(page === "Clips" || page === "Library") && (
            <>
              <div className="gallery-toolbar">
                <Badge tone="violet">{clips.length} CLIPS</Badge>
                <span>Original · MP4</span>
                <small>Más recientes primero</small>
              </div>
              {clips.length ? (
                gallery()
              ) : (
                <section className="panel">
                  <Empty
                    icon={<FolderOpen size={34} />}
                    title="Tu biblioteca está lista para empezar"
                    description="Conecta un directo y usa Crear clip. Tus archivos aparecerán aquí automáticamente."
                  />
                  <div className="empty-action">
                    <button
                      className="primary"
                      onClick={() => setPage("Live Monitor")}
                    >
                      <Radio size={16} /> Conectar transmisión
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
          {page === "Settings" && <SettingsPage studio={studio} />}
          {page === 'Moments' && <MomentsPage studio={studio}/>} 
          {page === 'Publish' && <PublishingPage studio={studio} notify={notify}/>} 
          {phase && (
            <section className="panel future">
              <Empty
                icon={<Sparkles size={30} />}
                title={`Preparado para la fase ${phase}`}
                description="Primero validamos el flujo Stream → Buffer → Transcripción → Clip. Esta función aún no está implementada."
              />
              <button
                className="secondary"
                onClick={() => setPage("Live Monitor")}
              >
                Volver al estudio <ArrowRight size={16} />
              </button>
            </section>
          )}
        </main>
        <footer className="statusbar">
          <span>
            <Cpu size={13} /> CPU{" "}
            <b>{resources ? `${resources.cpu.toFixed(0)}%` : "—"}</b>
          </span>
          <span>
            RAM{" "}
            <b>
              {resources
                ? `${resources.ram_used.toFixed(1)} / ${resources.ram_total.toFixed(0)} GB`
                : "—"}
            </b>
          </span>
          <span>
            GPU <b>N/D</b>
          </span>
          <span className="status-spacer" />
          <span>
            <Database size={12} /> BUFFER{" "}
            <b>{time(stream.buffer_seconds).slice(3)}</b>
          </span>
          <span>
            <HardDrive size={12} /> LIBRE{" "}
            <b>{resources ? `${resources.storage_free.toFixed(1)} GB` : "—"}</b>
          </span>
          <span className="local-indicator">
            <span className={`dot ${connected ? "green" : "red"}`} /> LOCAL
          </span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <span>{toast}</span>
          <button onClick={() => setToast("")} aria-label="Cerrar notificación">
            ×
          </button>
        </div>
      )}
      {selected && (
        <ClipModal
          clip={clips.find((c) => c.id === selected.id) || selected}
          close={() => setSelected(null)}
          notify={notify}
        />
      )}
    </div>
  );
}
