import { useEffect, useRef, useState } from "react";
import {
  Clapperboard,
  Download,
  X,
  LoaderCircle,
  Check,
  ArrowUpRight,
  Captions,
  RefreshCw,
  Smartphone,
} from "lucide-react";
import { api, time } from "./api";
import type { Clip, Transcript } from "./types";
import { ContentMetadataPanel } from "./metadata/ContentMetadataPanel";
import { PublishPanel } from "./publishing/PublishPanel";

export function Badge({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return (
    <span className={`badge ${tone}`}>
      <i />
      {children}
    </span>
  );
}
export function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric-label">
        {label}
        {icon}
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
export function Empty({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export function VideoPlayer({ src }: { src?: string }) {
  const [error, setError] = useState(false);
  useEffect(() => setError(false), [src]);
  return (
    <div className="video-wrap">
      <video src={src} controls preload="metadata" playsInline onError={() => setError(true)} />
      {error && <div className="video-error">No se pudo reproducir el clip.</div>}
    </div>
  );
}
export function TranscriptPanel({
  items,
  status,
}: {
  items: Transcript[];
  status: string;
}) {
  const scrollArea = useRef<HTMLDivElement>(null),
    follow = useRef(true);
  useEffect(() => {
    if (follow.current && scrollArea.current) {
      scrollArea.current.scrollTop = scrollArea.current.scrollHeight;
    }
  }, [items.length]);
  return (
    <section className="panel transcript">
      <div className="panel-heading">
        <h3>
          <Captions size={17} /> Transcripción
        </h3>
        <Badge tone={status === "ready" ? "green" : "muted"}>
          {status === "ready"
            ? "ACTIVA"
            : status === "loading"
              ? "CARGANDO"
              : status === "error"
                ? "ERROR"
                : "EN ESPERA"}
        </Badge>
      </div>
      <div
        className="transcript-scroll"
        ref={scrollArea}
        onScroll={(e) => {
          const t = e.currentTarget;
          follow.current = t.scrollHeight - t.scrollTop - t.clientHeight < 70;
        }}
      >
        {items.length ? (
          items.map((item, i) => (
            <article
              key={item.id}
              className={i === items.length - 1 ? "latest" : ""}
            >
              <time>{time(item.start)}</time>
              <p>{item.text}</p>
            </article>
          ))
        ) : (
          <Empty
            icon={<Captions />}
            title="Cada palabra, en contexto"
            description="La transcripción aparecerá aquí al procesar los primeros segmentos de audio."
          />
        )}
      </div>
      <footer>
        <span className="dot violet" /> Whisper local · detección de idioma
        automática
      </footer>
    </section>
  );
}
export function ClipCard({
  clip,
  onClick,
}: {
  clip: Clip;
  onClick: () => void;
}) {
  return (
    <button className="clip-card" onClick={onClick}>
      <div className="clip-thumb">
        {clip.status === "ready" ? (
          <img src={`/api/clips/${clip.id}/thumbnail`} alt="" />
        ) : (
          <Clapperboard size={30} />
        )}
        <span className="clip-duration">
          {clip.status === "ready"
            ? time(clip.duration).slice(3)
            : clip.status === "capturing"
              ? "−30s / +15s"
              : "MP4"}
        </span>
        {["capturing", "processing"].includes(clip.status) && (
          <LoaderCircle className="spin" />
        )}
      </div>
      <div className="clip-body">
        <div className="clip-meta">
          <Badge
            tone={
              clip.status === "ready"
                ? "green"
                : clip.status === "error"
                  ? "red"
                  : "violet"
            }
          >
            {clip.status.toUpperCase()}
          </Badge>
          <ArrowUpRight size={15} />
        </div>
        <h3>{clip.title}</h3>
        {clip.render_status !== "NOT_RENDERED" && (
          <small className={`render-badge ${clip.render_status.toLowerCase()}`}>
            9:16 · {clip.render_status === 'READY' ? 'LISTO' : `${clip.render_stage || clip.render_status} ${clip.render_progress}%`}
          </small>
        )}
        <small>
          {new Date(clip.created_at).toLocaleString("es")} · Original
        </small>
      </div>
    </button>
  );
}
export function ClipModal({ clip, close, notify }: { clip: Clip; close: () => void; notify: (message: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rendering, setRendering] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const requestRender = async (force = false) => {
    setRendering(true);
    try {
      await api<Clip>(`/clips/${clip.id}/render${force ? '/regenerate' : ''}`, {});
      notify(force ? 'Regeneración encolada. El original se conserva.' : 'Render vertical encolado. Puedes seguir trabajando.');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'No se pudo iniciar el render.');
    } finally { setRendering(false); }
  };
  return (
    <dialog
      ref={dialog}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-header">
        <span>
          <Clapperboard size={18} /> Detalles del clip
        </span>
        <button className="icon-button" onClick={close} aria-label="Cerrar">
          <X />
        </button>
      </div>
      {clip.status === "ready" ? (
        <div className={clip.render_status === 'READY' ? 'render-compare' : ''}>
          <div><small className="video-label">ORIGINAL</small><VideoPlayer src={`/api/clips/${clip.id}/video`} /></div>
          {clip.render_status === 'READY' && <div><small className="video-label">FINAL · 9:16</small><VideoPlayer src={`/api/clips/${clip.id}/vertical`} /></div>}
        </div>
      ) : (
        <Empty
          icon={
            clip.status === "error" ? <X /> : <LoaderCircle className="spin" />
          }
          title={
            clip.status === "capturing"
              ? "Completando la captura del intervalo seleccionado"
              : clip.status === "processing"
                ? "Procesando clip"
                : "No se pudo crear el clip"
          }
          description={
            clip.error ||
            "Puedes seguir trabajando mientras el clip se prepara."
          }
        />
      )}
      <div className="modal-content">
        <Badge tone={clip.status === "ready" ? "green" : "violet"}>
          {clip.status}
        </Badge>
        <h2>{clip.title}</h2>
        <p>Formato original · H.264 / AAC · {time(clip.duration)}</p>
        <div className={`render-state ${clip.render_status.toLowerCase()}`}>
          <Smartphone size={16} />
          <span>{clip.render_status === 'NOT_RENDERED' ? 'Aún no se generó una versión vertical.' : `Render ${clip.render_status} · ${clip.render_stage || 'preparando'} · ${clip.render_progress}%`}</span>
        </div>
        {clip.render_status === 'FAILED' && <p className="notice error">{clip.render_error || 'No se pudo procesar el clip.'}</p>}
        <div className="steps">
          <span>
            <Check size={14} /> Captura
          </span>
          <span>→</span>
          <span>Codificación</span>
          <span>→</span>
          <span>MP4 listo</span>
        </div>
        {clip.status === "ready" && (
          <div className="modal-actions">
            {clip.render_status !== 'READY' && <button className="primary" disabled={rendering || ['QUEUED','PROCESSING'].includes(clip.render_status)} onClick={()=>void requestRender(clip.render_status === 'FAILED')}><Captions size={16} /> {rendering || ['QUEUED','PROCESSING'].includes(clip.render_status) ? 'Renderizando…' : clip.render_status === 'FAILED' ? 'Reintentar render' : 'Generar formato vertical'}</button>}
            {clip.render_status === 'READY' && <button className="secondary" disabled={rendering} onClick={()=>void requestRender(true)}><RefreshCw size={16} /> Regenerar</button>}
            <a className="button secondary" href={`/api/clips/${clip.id}/video?download=true`}><Download size={16} /> Original</a>
            {clip.render_status === 'READY' && <><a className="button primary" href={`/api/clips/${clip.id}/vertical?download=true`}><Download size={16} /> Descargar 9:16</a>{clip.render_settings?.subtitles_enabled && <><a className="button secondary" href={`/api/clips/${clip.id}/subtitles/srt`}><Captions size={16} /> SRT</a><a className="button secondary" href={`/api/clips/${clip.id}/subtitles/ass`}><Captions size={16} /> ASS</a></>}</>}
          </div>
        )}
        {clip.render_status === 'READY' && <ContentMetadataPanel clipId={clip.id} notify={notify} />}
        {clip.render_status === 'READY' && <PublishPanel clipId={clip.id} notify={notify} />}
      </div>
    </dialog>
  );
}
