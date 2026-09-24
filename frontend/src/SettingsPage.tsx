import { Cpu, Settings } from "lucide-react";
import { ClipTimingSettings } from './ClipTimingSettings';
import { useState } from "react";
import { RulesManager } from "./detection/RulesManager";
import { AISettings } from './ai/AISettings';
import { RenderSettings } from './rendering/RenderSettings';
import { MetadataSettings } from './metadata/MetadataSettings';
import { SocialAccountsSettings } from './publishing/SocialAccountsSettings';
import { api } from "./api";
import { Badge } from "./components";
import { useStudio } from "./useStudio";
import type { Clip } from "./types";

export function SettingsPage({
  studio,
}: {
  studio: ReturnType<typeof useStudio>;
}) {
  const { stream, clips, transcripts, system, resources, connected } = studio;
  const [section, setSection] = useState("system");
  const active = ["starting", "live", "stopping"].includes(stream.state),
    ready = clips.filter((c) => c.status === "ready");
  return (
    <>
      <div className="settings-sections">
        <button className={section === 'clips' ? 'selected' : ''} onClick={() => setSection('clips')}>Duración de clips</button>
        <button className={section === 'ai' ? 'selected' : ''} onClick={()=>setSection('ai')}>AI</button>
        <button className={section === 'render' ? 'selected' : ''} onClick={()=>setSection('render')}>Subtítulos y formato</button>
        <button className={section === 'metadata' ? 'selected' : ''} onClick={()=>setSection('metadata')}>AI Content</button>
        <button className={section === 'social' ? 'selected' : ''} onClick={()=>setSection('social')}>Social Accounts</button>
        <button
          className={section === "system" ? "selected" : ""}
          onClick={() => setSection("system")}
        >
          Sistema
        </button>
        <button
          className={section === "detection" ? "selected" : ""}
          onClick={() => setSection("detection")}
        >
          Moment Detection
        </button>
      </div>
      {section === 'clips' ? <ClipTimingSettings studio={studio}/> : section === 'ai' ? <AISettings/> : section === 'render' ? <RenderSettings/> : section === 'metadata' ? <MetadataSettings/> : section === 'social' ? <SocialAccountsSettings/> : section === "detection" ? (
        <RulesManager />
      ) : (
        <div className="settings-grid">
          <section className="panel">
            <div className="panel-heading">
              <h3>
                <Cpu size={17} /> Sistema
              </h3>
              <Badge tone={connected ? "green" : "red"}>
                {connected ? "CONECTADO" : "OFFLINE"}
              </Badge>
            </div>
            {Object.entries({
              Backend: system?.backend || "offline",
              FFmpeg: system?.ffmpeg || "—",
              Whisper: stream.transcription_status,
              Modelo: system?.model || "—",
              Dispositivo: system?.device || "—",
              Grabación: system?.capture_mode === 'copy' ? 'Copia directa' : 'Recodificación',
              'Hilos de transcripción': system?.whisper_threads ?? '—',
              'Calidad preferida': system?.capture_max_height ? `${system.capture_max_height}p` : '—',
              'Fuentes simultáneas': '2',
              'Procesamiento de video': '1 trabajo a la vez',
              "Base de datos": system?.database || "—",
              RAM: resources ? `${resources.ram_total.toFixed(1)} GB` : "—",
            }).map(([k, v]) => (
              <div className="setting-row" key={k}>
                <span>{k}</span>
                <strong>{v}</strong>
              </div>
            ))}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h3>
                <Settings size={17} /> Preferencias de fase 1
              </h3>
            </div>
            <div className="setting-row">
              <span>Buffer</span>
              <strong>{stream.buffer_capacity / 60} minutos</strong>
            </div>
            <div className="setting-row">
              <span>Clip manual</span>
              <strong>{studio.clipTiming.before_seconds} s antes + {studio.clipTiming.after_seconds} s después</strong>
            </div>
            <div className="setting-row">
              <span>Salida</span>
              <strong>MP4 original · H.264</strong>
            </div>
            <div className="setting-row">
              <span>Transcripción</span>
              <strong>Local · idioma automático</strong>
            </div>
            <p className="settings-note">
              Las preferencias de captura se leen desde .env al iniciar el backend.
              Configura las reglas en Moment Detection y la evaluación local en AI.
            </p>
          </section>
        </div>
      )}
    </>
  );
}
