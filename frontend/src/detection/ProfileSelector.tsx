import { useState } from "react";
import { Layers } from "lucide-react";
import { api } from "../api";
import { useRules, rulesChanged } from "./useRules";
export function ProfileSelector() {
  const { config, error, reload } = useRules(),
    [busy, setBusy] = useState(false),
    [failure, setFailure] = useState("");
  return (
    <div className="profile-selector">
      <label>
        <Layers size={15} /> Detection Profile
        <select
          aria-label="Detection Profile"
          disabled={!config || busy}
          value={config?.active_profile_id || ""}
          onChange={async (e) => {
            const id = e.target.value;
            setBusy(true);
            setFailure("");
            try {
              await api("/moment-profiles/active", { profile_id: id || null });
              await reload();
              rulesChanged();
            } catch (e) {
              setFailure(
                e instanceof Error ? e.message : "No se cambió el perfil",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <option value="">Todas las reglas habilitadas</option>
          {config?.profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <span>
        {config?.active_rule_ids.length ?? 0} reglas efectivas · cambios en vivo
      </span>
      {(failure || error) && <p role="alert">{failure || error}</p>}
    </div>
  );
}
