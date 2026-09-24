import { useState } from "react";
import { Dialog } from "./Dialog";
import type { Configuration, Profile, ProfileInput } from "./types";
export function ProfileEditor({
  profile,
  config,
  save,
  close,
}: {
  profile: Profile | null;
  config: Configuration;
  save: (value: ProfileInput) => Promise<void>;
  close: () => void;
}) {
  const [value, setValue] = useState<ProfileInput>({
      name: profile?.name || "",
      group_ids: profile?.group_ids || [],
      rule_ids: profile?.rule_ids || [],
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const toggle = (field: "group_ids" | "rule_ids", id: string) =>
    setValue((current) => ({
      ...current,
      [field]: current[field].includes(id)
        ? current[field].filter((value) => value !== id)
        : [...current[field], id],
    }));
  return (
    <Dialog
      title={profile ? "Editar perfil" : "Nuevo perfil"}
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
            setError(e instanceof Error ? e.message : "No se guardó el perfil");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Nombre del perfil
          <input
            required
            autoFocus
            maxLength={100}
            value={value.name}
            onChange={(e) => setValue({ ...value, name: e.target.value })}
          />
        </label>
        <p className="rules-help">
          Incluye todos los miembros de los grupos elegidos y las reglas
          individuales marcadas. Los interruptores de regla y grupo siguen
          teniendo prioridad.
        </p>
        <div className="rules-form-grid">
          <fieldset>
            <legend>Grupos completos</legend>
            <div className="rule-selection">
              {config.groups.length ? (
                config.groups.map((group) => (
                  <label key={group.id}>
                    <input
                      type="checkbox"
                      checked={value.group_ids.includes(group.id)}
                      onChange={() => toggle("group_ids", group.id)}
                    />
                    {group.name}
                    {!group.enabled && <small>Desactivado</small>}
                  </label>
                ))
              ) : (
                <p className="rules-help">Aún no hay grupos.</p>
              )}
            </div>
          </fieldset>
          <fieldset>
            <legend>Reglas individuales</legend>
            <div className="rule-selection">
              {config.rules.length ? (
                config.rules.map((rule) => (
                  <label key={rule.id}>
                    <input
                      type="checkbox"
                      checked={value.rule_ids.includes(rule.id)}
                      onChange={() => toggle("rule_ids", rule.id)}
                    />
                    {rule.name}
                    {!rule.enabled && <small>Desactivada</small>}
                  </label>
                ))
              ) : (
                <p className="rules-help">Aún no hay reglas.</p>
              )}
            </div>
          </fieldset>
        </div>
        {!value.group_ids.length && !value.rule_ids.length && (
          <p className="rules-help">
            Este perfil estará vacío: no aportará señales lingüísticas.
          </p>
        )}
        {error && (
          <div role="alert" className="notice error">
            {error}
          </div>
        )}
        <footer>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            Cancelar
          </button>
          <button className="primary" disabled={busy}>
            Guardar perfil
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
