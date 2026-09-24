import { useEffect, useState } from "react";
import { api } from "../api";
import type { RenderSettings as RenderConfig, RenderStatus } from "../types";

const numericFields: Array<[keyof RenderConfig, string, number, number, number]> = [
  ['output_width', 'Ancho de salida', 240, 2160, 2], ['output_height', 'Alto de salida', 426, 3840, 2],
  ['crf', 'Calidad (CRF)', 16, 32, 1], ['fps', 'FPS (0 conserva fuente)', 0, 60, 1],
  ['safe_area_top', 'Área segura superior', 0, 800, 10], ['safe_area_bottom', 'Área segura inferior', 0, 900, 10],
  ['safe_area_left', 'Área segura izquierda', 0, 500, 10], ['safe_area_right', 'Área segura derecha', 0, 500, 10],
  ['font_size', 'Tamaño de fuente', 18, 180, 1], ['outline_size', 'Contorno', 0, 16, 1],
  ['max_lines', 'Máximo de líneas', 1, 3, 1], ['max_chars_per_line', 'Caracteres por línea', 12, 70, 1],
  ['min_subtitle_duration', 'Duración mínima (s)', .1, 4, .1], ['max_subtitle_duration', 'Duración máxima (s)', .5, 10, .1],
];

export function RenderSettings() {
  const [config, setConfig] = useState<RenderConfig | null>(null);
  const [status, setStatus] = useState<RenderStatus | null>(null);
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    void Promise.all([api<RenderConfig>('/render/settings'), api<RenderStatus>('/render/status')])
      .then(([settings, render]) => { setConfig(settings); setStatus(render); })
      .catch(error => setMessage(error instanceof Error ? error.message : 'No se pudo cargar la configuración.'));
  }, []);
  const change = <K extends keyof RenderConfig>(key: K, value: RenderConfig[K]) =>
    setConfig(current => current ? { ...current, [key]: value } : current);
  const save = async () => {
    if (!config) return;
    setSaving(true); setMessage('');
    try { setConfig(await api<RenderConfig>('/render/settings', config, 'PUT')); setMessage('Configuración de exportación guardada.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo guardar.'); }
    finally { setSaving(false); }
  };
  if (!config) return <section className="panel render-settings"><p>Cargando configuración de render…</p></section>;
  return <section className="panel render-settings">
    <div className="render-heading"><div><span>FASE 4 + 5 · LOCAL</span><h2>Subtítulos y formato vertical</h2><p>FFmpeg genera un MP4 9:16 desde el clip y su transcripción existente. El original nunca se modifica.</p></div><small>Render {status?.status || '—'} · cola {status?.queued || 0} · 1 a la vez</small></div>
    {message && <p className={message.includes('guardada') ? 'notice' : 'notice error'}>{message}</p>}
    <div className="render-config-grid">
      <fieldset><legend>Video y reencuadre</legend>
        <label>Modo de reencuadre<select value={config.reframing_mode} onChange={e=>change('reframing_mode',e.target.value as RenderConfig['reframing_mode'])}><option value="CENTER_CROP">Center crop</option><option value="SMART_CROP">Smart crop (fallback centro)</option><option value="SUBJECT_TRACKING">Seguimiento (fallback centro)</option></select></label>
        <label>Fondo<select value={config.background_mode} onChange={e=>change('background_mode',e.target.value as RenderConfig['background_mode'])}><option value="CROP">Recorte vertical</option><option value="BLUR">Fondo desenfocado</option><option value="BLACK">Fondo negro</option></select></label>
        {numericFields.slice(0, 8).map(([key,label,min,max,step])=><label key={key}>{label}<input type="number" min={min} max={max} step={step} value={config[key] as number} onChange={e=>change(key,Number(e.target.value) as RenderConfig[typeof key])}/></label>)}
      </fieldset>
      <fieldset><legend>Subtítulos quemados</legend>
        <label className="render-toggle"><input type="checkbox" checked={config.subtitles_enabled} onChange={e=>change('subtitles_enabled',e.target.checked)}/> Incluir subtítulos en el MP4</label>
        <label>Estilo<select value={config.subtitle_style} onChange={e=>change('subtitle_style',e.target.value as RenderConfig['subtitle_style'])}><option value="STANDARD">Estándar</option><option value="DYNAMIC">Dinámico</option></select></label>
        <label>Posición<select value={config.subtitle_position} onChange={e=>change('subtitle_position',e.target.value as RenderConfig['subtitle_position'])}><option value="TOP">Superior</option><option value="MIDDLE">Centro</option><option value="BOTTOM">Inferior</option></select></label>
        <label>Fuente<input value={config.font} maxLength={120} onChange={e=>change('font',e.target.value)}/></label>
        <label>Color<input type="color" value={config.font_color} onChange={e=>change('font_color',e.target.value.toUpperCase())}/></label>
        {numericFields.slice(8).map(([key,label,min,max,step])=><label key={key}>{label}<input type="number" min={min} max={max} step={step} value={config[key] as number} onChange={e=>change(key,Number(e.target.value) as RenderConfig[typeof key])}/></label>)}
        <label className="render-toggle"><input type="checkbox" checked={config.background} onChange={e=>change('background',e.target.checked)}/> Fondo semitransparente</label>
        <label className="render-toggle"><input type="checkbox" checked={config.highlight_words} onChange={e=>change('highlight_words',e.target.checked)}/> Resaltar palabras si Whisper aporta tiempos por palabra</label>
        <label className="render-toggle"><input type="checkbox" checked={config.animation_enabled} onChange={e=>change('animation_enabled',e.target.checked)}/> Animación sencilla</label>
      </fieldset>
    </div>
    <div className="ai-actions"><button className="primary" disabled={saving} onClick={()=>void save()}>{saving ? 'Guardando…' : 'Guardar configuración'}</button></div>
  </section>;
}
