import { Activity } from "lucide-react";
import type { Evaluation } from "./types";
export function SignalPanel({ evaluation }: { evaluation: Evaluation | null }) {
  return (
    <section className="signal-panel">
      <div>
        <h3>
          <Activity size={15} /> Señales del diccionario
        </h3>
        <span>
          {evaluation?.has_audio
            ? `${evaluation.window_seconds?.toFixed(0)} s de contexto · ${evaluation.language}`
            : "Esperando audio"}
        </span>
      </div>
      <div className="signal-score">
        <strong>{(evaluation?.detection_confidence ?? 0).toFixed(2)}</strong>
        <span>
          Confianza lingüística
          <br />
          <small>Se combina con duración y estructura</small>
        </span>
      </div>
      <div className="signal-matches">
        {evaluation?.matches.length ? (
          evaluation.matches.map((match) => (
            <span key={match.rule_id} title={match.pattern}>
              {match.name}{" "}
              <b>
                {match.weight >= 0 ? "+" : ""}
                {match.weight.toFixed(2)}
              </b>
            </span>
          ))
        ) : (
          <p>
            Sin coincidencias en la ventana actual. Configura las reglas en
            Settings → Moment Detection.
          </p>
        )}
      </div>
    </section>
  );
}
