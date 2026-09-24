import { useEffect, useState } from "react";
import { api } from "../api";

interface Config {
  auto_generate_metadata: boolean;
  style: "BALANCED" | "VIRAL" | "CLEAN" | "AGGRESSIVE";
  hashtag_count: number;
  context_before_seconds: number;
  context_after_seconds: number;
  max_context_chars: number;
  streamer_name: string;
  streamer_main_topics: string[];
  streamer_metadata_style: string;
}

export function MetadataSettings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => { void api<Config>("/metadata/settings").then(setConfig).catch((error) => setMessage(error.message)); }, []);
  if (!config) return <section className="panel metadata-settings">{message || "Cargando AI Content…"}</section>;
  const update = <K extends keyof Config>(key: K, value: Config[K]) => setConfig({ ...config, [key]: value });
  const save = async () => {
    try { setConfig(await api<Config>("/metadata/settings", config, "PUT")); setMessage("Configuración de metadata guardada."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "No se pudo guardar."); }
  };
  return <section className="panel ai-settings metadata-settings">
    <div><span className="eyebrow">AI CONTENT · OLLAMA LOCAL</span><h2>Prepara cada clip para publicar.</h2>
      <p>Genera metadata después del render final, reutilizando la transcripción, el momento y su evaluación.</p></div>
    <div className="ai-toggles"><label><input type="checkbox" checked={config.auto_generate_metadata} onChange={(event) => update("auto_generate_metadata", event.target.checked)} />Generar automáticamente al terminar el render 9:16</label></div>
    <div className="ai-form-grid">
      <label>Estilo<select value={config.style} onChange={(event) => update("style", event.target.value as Config["style"])}><option>BALANCED</option><option>VIRAL</option><option>CLEAN</option><option>AGGRESSIVE</option></select></label>
      <label>Hashtags por plataforma<input type="number" min={3} max={8} value={config.hashtag_count} onChange={(event) => update("hashtag_count", Number(event.target.value))} /></label>
      <label>Contexto anterior (s)<input type="number" min={0} max={30} value={config.context_before_seconds} onChange={(event) => update("context_before_seconds", Number(event.target.value))} /></label>
      <label>Contexto posterior (s)<input type="number" min={0} max={30} value={config.context_after_seconds} onChange={(event) => update("context_after_seconds", Number(event.target.value))} /></label>
      <label>Nombre del streamer<input value={config.streamer_name} placeholder="Opcional" onChange={(event) => update("streamer_name", event.target.value)} /></label>
      <label>Temas principales<input value={config.streamer_main_topics.join(", ")} placeholder="Dota 2, Gaming, Esports" onChange={(event) => update("streamer_main_topics", event.target.value.split(",").map((v) => v.trim()).filter(Boolean))} /></label>
      <label className="wide">Estilo del streamer<input value={config.streamer_metadata_style} placeholder="energético, corto, internet-native" onChange={(event) => update("streamer_metadata_style", event.target.value)} /></label>
    </div>
    {message && <div className="notice">{message}</div>}
    <div className="ai-actions"><button className="primary" onClick={() => void save()}>Guardar configuración</button></div>
  </section>;
}
