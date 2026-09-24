import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { api } from "../api";
import type { Evaluation } from "./types";
export function RuleTester({ revision }: { revision: number }) {
  const [text, setText] = useState(""),
    [language, setLanguage] = useState("*"),
    [result, setResult] = useState<Evaluation | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => setResult(null), [revision, text, language]);
  return (
    <div className="rule-tester">
      <div>
        <h3>
          <FlaskConical size={18} /> Laboratorio de reglas
        </h3>
        <p className="rules-help">
          Prueba el perfil actual con un texto. La confianza mostrada es una
          suma de señales limitada a 0–1, no una probabilidad de viralidad ni
          una orden para crear un clip.
        </p>
      </div>
      <form
        className="rules-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            setResult(
              await api<Evaluation>("/moment-rules/preview", {
                text,
                language,
              }),
            );
          } catch (e) {
            setError(e instanceof Error ? e.message : "Error de evaluación");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Texto de prueba
          <textarea
            required
            maxLength={20000}
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <div className="rules-test-controls">
          <label>
            Idioma del texto
            <input
              required
              maxLength={35}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              placeholder="Código de idioma"
            />
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Evaluando…" : "Probar reglas activas"}
          </button>
        </div>
        <p className="rules-help">
          * significa idioma desconocido: solo se aplican reglas universales.
          Las coincidencias son literales; se normalizan espacios y Unicode y se
          conservan los acentos.
        </p>
      </form>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {result && (
        <section className="rule-test-result">
          <div className="rule-result-metrics">
            <strong>
              {result.detection_confidence.toFixed(2)}
              <small>Confianza lingüística</small>
            </strong>
            <strong>
              {result.matches.length}
              <small>Reglas coincidentes</small>
            </strong>
            <strong>
              {result.linguistic_weight.toFixed(2)}
              <small>Suma de pesos</small>
            </strong>
          </div>
          {result.matches.length ? (
            result.matches.map((match) => (
              <div className="rule-match" key={match.rule_id}>
                <span>
                  {match.name} <small>“{match.pattern}”</small>
                </span>
                <b>
                  {match.weight >= 0 ? "+" : ""}
                  {match.weight.toFixed(2)}
                </b>
              </div>
            ))
          ) : (
            <p className="rules-help">
              Ninguna regla activa coincide con este texto e idioma.
            </p>
          )}
          <p className="rules-help">
            Solo señales · no crea momentos ni clips · revisión{" "}
            {result.revision}
          </p>
        </section>
      )}
    </div>
  );
}
