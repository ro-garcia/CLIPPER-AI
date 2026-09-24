import { useState } from "react";
import {
  Link,
  LoaderCircle,
  Zap,
  ArrowRight,
  ShieldCheck,
  HardDrive,
  Radio,
} from "lucide-react";
import { api } from "./api";
import type { StreamInfo, StreamState } from "./types";
export function SourcePanel({
  active,
  onStarted,
  notify,
}: {
  active: boolean;
  onStarted: (streamId: string | null) => void;
  notify: (message: string) => void;
}) {
  const [url, setUrl] = useState(""),
    [info, setInfo] = useState<StreamInfo | null>(null),
    [busy, setBusy] = useState("");
  async function action(name: string, work: () => Promise<void>) {
    setBusy(name);
    try {
      await work();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Error de conexión");
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="source-panel">
      <div className="source-copy">
        <span className="eyebrow">
          <span className="dot violet" /> TU PRÓXIMO GRAN CLIP EMPIEZA AQUÍ
        </span>
        <h2>Dos directos. Un solo estudio.</h2>
        <p>Agrega hasta dos fuentes y crea clips de cada una por separado.</p>
      </div>
      <form
        className="source-form"
        onSubmit={(e) => {
          e.preventDefault();
          void action("analyze", async () =>
            setInfo(await api<StreamInfo>("/streams/analyze", { url })),
          );
        }}
      >
        <div className="url-input">
          <Link size={17} />
          <input
            aria-label="URL de la transmisión"
            type="url"
            placeholder="Pega el enlace de tu transmisión…"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setInfo(null);
            }}
            required
            disabled={active}
          />
        </div>
        <button className="primary" disabled={!!busy || active}>
          {busy === "analyze" ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Zap size={16} />
          )}{" "}
          Analizar enlace <ArrowRight size={16} />
        </button>
      </form>
      <div className="source-foot">
        <span>
          <ShieldCheck size={13} /> Procesamiento local
        </span>
        <span>
          <HardDrive size={13} /> Solo se conserva el buffer
        </span>
        <span>HTTP · HLS · plataformas compatibles con yt-dlp</span>
      </div>
      {busy === "analyze" && <div className="skeleton analysis-skeleton" />}
      {info && (
        <div className="source-result">
          {info.thumbnail && <img src={info.thumbnail} alt="" />}
          <div>
            <strong>{info.title}</strong>
            <small>
              {info.platform} ·{" "}
              {info.is_live ? "En directo" : "Video / fuente compatible"} ·{" "}
              {info.height ? `${info.height}p` : "Resolución por detectar"}
            </small>
          </div>
          <button
            className="primary"
            disabled={!!busy || active}
            onClick={() =>
              void action("start", async () => {
                const source = await api<StreamState>("/streams/start", { url });
                setInfo(null);
                setUrl('');
                onStarted(source.stream_id);
                notify("Conectando la transmisión…");
              })
            }
          >
            {busy === "start" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Radio size={16} />
            )}{" "}
            Iniciar monitoreo
          </button>
        </div>
      )}
    </section>
  );
}
