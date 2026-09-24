import { useState } from "react";
import { Dialog } from "./Dialog";
import {
  ruleTypes,
  matchTypes,
  labels,
  type RuleInput,
  type Rule,
  type Group,
} from "./types";
const blank: RuleInput = {
  name: "",
  pattern: "",
  rule_type: "KEYWORD",
  category: "",
  weight: 0.1,
  language: "*",
  match_type: "CONTAINS",
  case_sensitive: false,
  enabled: true,
  group_id: null,
};
export function RuleEditor({
  rule,
  groups,
  save,
  close,
}: {
  rule: Rule | null;
  groups: Group[];
  save: (value: RuleInput) => Promise<void>;
  close: () => void;
}) {
  const [value, setValue] = useState<RuleInput>(
      rule
        ? (Object.fromEntries(
            Object.keys(blank).map((key) => [
              key,
              rule[key as keyof RuleInput],
            ]),
          ) as unknown as RuleInput)
        : blank,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const change = <K extends keyof RuleInput>(key: K, next: RuleInput[K]) =>
    setValue((value) => ({ ...value, [key]: next }));
  return (
    <Dialog
      title={rule ? "Editar regla" : "Nueva regla"}
      close={close}
      busy={busy}
    >
      <form
        className="rules-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await save(value);
            close();
          } catch (e) {
            setError(e instanceof Error ? e.message : "No se guardó la regla");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Nombre
          <input
            required
            maxLength={100}
            value={value.name}
            onChange={(e) => change("name", e.target.value)}
            autoFocus
          />
        </label>
        <label>
          Palabra, frase o patrón literal
          <textarea
            required
            maxLength={500}
            rows={2}
            value={value.pattern}
            onChange={(e) => change("pattern", e.target.value)}
          />
        </label>
        <div className="rules-form-grid">
          <label>
            Tipo
            <select
              value={value.rule_type}
              onChange={(e) =>
                change("rule_type", e.target.value as RuleInput["rule_type"])
              }
            >
              {ruleTypes.map((type) => (
                <option key={type} value={type}>
                  {labels[type]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Grupo
            <select
              value={value.group_id || ""}
              onChange={(e) => change("group_id", e.target.value || null)}
            >
              <option value="">Sin grupo</option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                  {group.enabled ? "" : " · desactivado"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Categoría
            <input
              maxLength={100}
              value={value.category}
              onChange={(e) => change("category", e.target.value)}
            />
          </label>
          <label>
            Peso (−1 a +1)
            <input
              required
              type="number"
              step="0.01"
              min={-1}
              max={1}
              value={value.weight}
              onChange={(e) => change("weight", e.target.valueAsNumber)}
            />
          </label>
          <label>
            Idioma · código o *
            <input
              required
              maxLength={35}
              pattern="\*|[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*"
              value={value.language}
              onChange={(e) => change("language", e.target.value)}
              placeholder="* = todos los idiomas"
            />
          </label>
          <label>
            Coincidencia
            <select
              value={value.match_type}
              onChange={(e) =>
                change("match_type", e.target.value as RuleInput["match_type"])
              }
            >
              {matchTypes.map((type) => (
                <option key={type} value={type}>
                  {labels[type]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="rules-checks">
          <label>
            <input
              type="checkbox"
              checked={value.enabled}
              onChange={(e) => change("enabled", e.target.checked)}
            />{" "}
            Activada
          </label>
          <label>
            <input
              type="checkbox"
              checked={value.case_sensitive}
              onChange={(e) => change("case_sensitive", e.target.checked)}
            />{" "}
            Distinguir mayúsculas
          </label>
        </div>
        <p className="rules-help">
          Texto literal, sin expresiones regulares. Cada regla aporta su peso
          una vez por ventana. Un peso negativo reduce la señal.
        </p>
        {error && (
          <div role="alert" className="notice error">
            {error}
          </div>
        )}
        <footer>
          <button
            type="button"
            className="secondary"
            onClick={close}
            disabled={busy}
          >
            Cancelar
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Guardando…" : "Guardar regla"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
