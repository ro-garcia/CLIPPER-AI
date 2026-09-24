import { CalendarClock, ExternalLink, RefreshCw, Send, ShieldCheck, X } from "lucide-react";
import { api } from "../api";
import { Badge, Empty } from "../components";
import { useStudio } from "../useStudio";
import type { PublicationJob } from "../types";

export function PublishingPage({ studio, notify }: { studio: ReturnType<typeof useStudio>; notify: (value: string) => void }) {
  const { publications, publishing } = studio;
  async function action(job: PublicationJob, kind: "retry" | "cancel") {
    try { await api(`/publishing/jobs/${job.id}/${kind}`, {}); notify(kind === "retry" ? "Publicación encolada nuevamente." : "Publicación cancelada."); }
    catch (error) { notify(error instanceof Error ? error.message : "No se pudo completar la acción."); }
  }
  return <div className="publishing-page">
    {publishing?.safe_publish_mode && <div className="safe-mode-banner"><ShieldCheck size={18}/><div><strong>SAFE PUBLISH MODE</strong><p>Las publicaciones son simuladas. Ningún contenido saldrá de tu equipo.</p></div><Badge tone="green">MOCK</Badge></div>}
    <div className="publication-summary">
      <span>EN COLA <b>{publishing?.queued || 0}</b></span><span>ACTIVAS <b>{publishing?.active_count || 0}</b></span>
      <span>PROGRAMADAS <b>{publishing?.scheduled || 0}</b></span><span>PUBLICADAS <b>{publications.filter((job) => job.status === "PUBLISHED").length}</b></span>
    </div>
    <section className="panel publication-queue"><div className="panel-heading"><h3><Send size={17}/> Publication queue</h3><small>Jobs independientes por plataforma</small></div>
      {!publications.length ? <Empty icon={<Send size={27}/>} title="No hay publicaciones todavía" description="Abre un clip READY TO PUBLISH y selecciona las plataformas."/> :
        <div className="publication-list">{publications.map((job) => <article className="publication-row" key={job.id}>
          <div className={`platform-mark ${job.platform}`}>{job.platform.slice(0, 1).toUpperCase()}</div>
          <div className="publication-main"><div><strong>{job.platform.replace("youtube", "YouTube Shorts")}</strong><Status status={job.status}/></div>
            <p>Clip {job.clip_id.slice(0, 8)} · {job.account_name}</p>
            {job.scheduled_at && <small><CalendarClock size={11}/>{new Date(job.scheduled_at).toLocaleString()}</small>}
            {job.last_error && <small className="publication-error">{job.error_code}: {job.last_error}</small>}
            {job.progress !== null && <div className="publish-progress"><i style={{width:`${job.progress}%`}}/></div>}
          </div>
          <div className="publication-actions">
            {job.publication_url && <a className="icon-button" href={job.publication_url} target="_blank" rel="noreferrer" title="Abrir publicación"><ExternalLink size={15}/></a>}
            {["FAILED","AUTH_REQUIRED"].includes(job.status) && <button className="icon-button" onClick={() => void action(job, "retry")} title="Reintentar"><RefreshCw size={15}/></button>}
            {["QUEUED","SCHEDULED","RETRYING"].includes(job.status) && <button className="icon-button" onClick={() => void action(job, "cancel")} title="Cancelar"><X size={15}/></button>}
          </div>
        </article>)}</div>}
    </section>
  </div>;
}

export function Status({ status }: { status: string }) {
  return <span className={`publication-status ${status.toLowerCase()}`}><i/>{status.replaceAll("_", " ")}</span>;
}
