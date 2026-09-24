import { useEffect, useState } from 'react';
import { api } from './api';
import type { useStudio } from './useStudio';

export function ClipTimingSettings({ studio }: { studio: ReturnType<typeof useStudio> }) {
  const { before_seconds, after_seconds } = studio.clipTiming;
  const [before, setBefore] = useState(String(before_seconds));
  const [after, setAfter] = useState(String(after_seconds));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => { setBefore(String(before_seconds)); setAfter(String(after_seconds)); }, [before_seconds, after_seconds]);
  const total = Number(before) + Number(after);
  const valid = before !== '' && after !== '' && Number.isInteger(Number(before)) && Number.isInteger(Number(after)) && Number(before) >= 1 && Number(before) <= studio.stream.buffer_capacity && Number(after) >= 0 && total <= 300;
  return <section className="panel clip-timing">
    <h3>Duración de clips</h3>
    <p>Elige cuánto conservar antes y después de pulsar Crear clip.</p>
    <form onSubmit={async event => {
      event.preventDefault();
      if (!valid || busy) return;
      setBusy(true); setMessage('');
      try {
        const saved = await api<typeof studio.clipTiming>('/settings/clips', { before_seconds: Number(before), after_seconds: Number(after) }, 'PUT');
        studio.setClipTiming(saved);
        setMessage('Guardado. Se aplicará a los nuevos clips de ambas fuentes.');
      } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo guardar.'); }
      finally { setBusy(false); }
    }}>
      <div className="clip-timing-fields">
        <label>Antes del clic (segundos)<input type="number" min={1} max={Math.min(300, studio.stream.buffer_capacity)} step={1} required value={before} disabled={busy} onChange={e => { setBefore(e.target.value); setMessage(''); }} /></label>
        <label>Después del clic (segundos)<input type="number" min={0} max={299} step={1} required value={after} disabled={busy} onChange={e => { setAfter(e.target.value); setMessage(''); }} /></label>
      </div>
      <p><strong>Duración total: {Number.isFinite(total) ? total : '—'} segundos</strong> · máximo 5 minutos</p>
      <p>Necesitas {before || '0'} segundos de buffer. Con 0 segundos después, no se agrega tiempo posterior al clic; el último segmento aún debe terminar de grabarse.</p>
      <button className="primary" disabled={!valid || busy || !studio.connected}>{busy ? 'Guardando…' : 'Guardar duración'}</button>
      {message && <p role="status">{message}</p>}
    </form>
    <small>Aplica a clips manuales. Los clips creados desde Moments conservan la duración del momento detectado.</small>
  </section>;
}
