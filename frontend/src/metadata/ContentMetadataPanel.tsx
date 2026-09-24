import { useEffect, useState } from "react";
import { Check, LoaderCircle, RefreshCw, Save, Sparkles } from "lucide-react";
import { api } from "../api";
import type { ContentMetadata } from "../types";

type Tab = "general" | "tiktok" | "youtube_shorts" | "instagram_reels" | "facebook_reels";
type Scope = "TODO" | "TITLE" | "CAPTION" | "HASHTAGS" | "COVER_TEXT";
const tabs: [Tab, string][] = [["general", "GENERAL"], ["tiktok", "TIKTOK"],
  ["youtube_shorts", "YOUTUBE"], ["instagram_reels", "INSTAGRAM"], ["facebook_reels", "FACEBOOK"]];

export function ContentMetadataPanel({ clipId, notify }: { clipId: string; notify: (value: string) => void }) {
  const [value, setValue] = useState<ContentMetadata | null>(null);
  const [tab, setTab] = useState<Tab>("general");
  const [busy, setBusy] = useState("");

  const load = () => api<ContentMetadata>(`/clips/${clipId}/metadata`).then(setValue)
    .catch((error) => notify(error instanceof Error ? error.message : "No se pudo cargar la metadata."));
  useEffect(() => { void load(); }, [clipId]);
  useEffect(() => {
    if (value?.status !== "METADATA_GENERATING") return;
    const timer = setInterval(() => void load(), 1200);
    return () => clearInterval(timer);
  }, [value?.status, clipId]);

  async function generate(scope: Scope) {
    setBusy(scope);
    try {
      const response = await api<ContentMetadata>(`/clips/${clipId}/metadata/generate`, { scope });
      setValue(response);
      notify(scope === "TODO" ? "Generación de contenido iniciada." : "Regeneración iniciada.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo generar la metadata.");
      await load();
    } finally { setBusy(""); }
  }

  async function save() {
    if (!value?.general || !value.platforms) return;
    setBusy("SAVE");
    try {
      const response = await api<ContentMetadata>(`/clips/${clipId}/metadata`, {
        general: value.general, platforms: value.platforms,
      }, "PUT");
      setValue(response);
      notify("Metadata guardada. El clip está listo para publicar.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo guardar.");
    } finally { setBusy(""); }
  }

  const updateGeneral = (key: string, next: string | string[]) => setValue((current) =>
    current?.general ? { ...current, general: { ...current.general, [key]: next } } : current);
  const updatePlatform = (key: string, next: string | string[]) => setValue((current) => {
    if (!current?.platforms || tab === "general") return current;
    return { ...current, platforms: { ...current.platforms,
      [tab]: { ...current.platforms[tab], [key]: next } } };
  });
  const tagList = (text: string) => text.split(/[\s,]+/).map((tag) => tag.trim()).filter(Boolean);

  if (!value) return <section className="metadata-panel metadata-loading"><LoaderCircle className="spin" /> Cargando AI Content…</section>;
  if (!value.general || !value.platforms) return (
    <section className="metadata-panel metadata-empty">
      <Sparkles size={22} /><div><h3>AI Content</h3><p>{value.error || "Genera títulos, captions y hashtags usando Ollama local."}</p></div>
      <button className="primary" disabled={value.status === "METADATA_GENERATING" || !!busy} onClick={() => void generate("TODO")}>
        {value.status === "METADATA_GENERATING" ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}
        {value.status === "METADATA_FAILED" ? "Reintentar" : value.status === "METADATA_GENERATING" ? "Generando…" : "Generar metadata"}
      </button>
    </section>
  );

  const platform = tab === "general" ? null : value.platforms[tab];
  return (
    <section className="metadata-panel">
      <div className="metadata-heading">
        <div><span>AI CONTENT</span><h3>{value.publication_status === "READY_TO_PUBLISH" ? "Clip ready to publish" : "Contenido del clip"}</h3></div>
        <span className={`metadata-ready ${value.status === "METADATA_READY" ? "ready" : ""}`}>
          {value.status === "METADATA_READY" && <Check size={13} />}{value.status.replaceAll("_", " ")}
        </span>
      </div>
      {value.error && <p className="notice error">{value.error}</p>}
      <div className="metadata-tabs">{tabs.map(([id, label]) =>
        <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
      {tab === "general" ? <div className="metadata-form">
        <Field label="Title" value={value.general.title} onChange={(next) => updateGeneral("title", next)} />
        <VariantPicker values={value.general.title_variants} selected={value.general.title} onSelect={(next) => updateGeneral("title", next)} />
        <Field label="Cover text" value={value.general.cover_text} onChange={(next) => updateGeneral("cover_text", next)} />
        <VariantPicker values={value.general.cover_text_variants} selected={value.general.cover_text} onSelect={(next) => updateGeneral("cover_text", next)} />
        <Field area label="Description" value={value.general.description} onChange={(next) => updateGeneral("description", next)} />
        <Field area label="Caption" value={value.general.caption} onChange={(next) => updateGeneral("caption", next)} />
        <Field label="Hashtags" value={value.general.hashtags.join(" ")} onChange={(next) => updateGeneral("hashtags", tagList(next))} />
        <Field label="Keywords" value={value.general.keywords.join(", ")} onChange={(next) => updateGeneral("keywords", next.split(",").map((v) => v.trim()).filter(Boolean))} />
        <div className="metadata-classification"><span>TOPIC <b>{value.general.topic}</b></span><span>TYPE <b>{value.general.content_type}</b></span><span>CATEGORY <b>{value.general.category}</b></span></div>
      </div> : platform && <div className="metadata-form">
        {"title" in platform && <Field label="Title" value={platform.title} onChange={(next) => updatePlatform("title", next)} />}
        {"description" in platform && <Field area label="Description" value={platform.description} onChange={(next) => updatePlatform("description", next)} />}
        {"caption" in platform && <Field area label="Caption" value={platform.caption} onChange={(next) => updatePlatform("caption", next)} />}
        <Field label="Hashtags" value={platform.hashtags.join(" ")} onChange={(next) => updatePlatform("hashtags", tagList(next))} />
      </div>}
      <div className="metadata-actions">
        <button className="primary" disabled={!!busy || value.status === "METADATA_GENERATING"} onClick={() => void save()}><Save size={15} /> Guardar</button>
        <select aria-label="Campo a regenerar" disabled={!!busy} defaultValue="TODO" id={`regen-${clipId}`}>
          <option value="TODO">Todo</option><option value="TITLE">Título</option><option value="CAPTION">Caption</option><option value="HASHTAGS">Hashtags</option><option value="COVER_TEXT">Cover text</option>
        </select>
        <button className="secondary" disabled={!!busy || value.status === "METADATA_GENERATING"} onClick={() => {
          const select = document.getElementById(`regen-${clipId}`) as HTMLSelectElement;
          void generate(select.value as Scope);
        }}><RefreshCw size={15} /> Regenerar</button>
      </div>
    </section>
  );
}

function Field({ label, value, onChange, area = false }: { label: string; value: string; onChange: (value: string) => void; area?: boolean }) {
  return <label className={area ? "metadata-field wide" : "metadata-field"}><span>{label}</span>
    {area ? <textarea value={value} rows={3} onChange={(event) => onChange(event.target.value)} /> :
      <input value={value} onChange={(event) => onChange(event.target.value)} />}</label>;
}

function VariantPicker({ values, selected, onSelect }: { values: string[]; selected: string; onSelect: (value: string) => void }) {
  return <div className="metadata-variants">{values.map((value, index) =>
    <button key={`${value}-${index}`} className={value === selected ? "active" : ""} onClick={() => onSelect(value)}>
      <small>{index === 0 ? "RECOMMENDED" : `ALT ${index}`}</small>{value}
    </button>)}</div>;
}
