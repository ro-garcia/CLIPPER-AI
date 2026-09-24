import { useState } from "react";
import { Dialog } from "./Dialog";
import type { Group } from "./types";
export function GroupEditor({
  group,
  save,
  close,
}: {
  group: Group | null;
  save: (value: { name: string; enabled: boolean }) => Promise<void>;
  close: () => void;
}) {
  const [name, setName] = useState(group?.name || ""),
    [enabled, setEnabled] = useState(group?.enabled ?? true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Dialog
      title={group ? "Editar grupo" : "Nuevo grupo"}
      close={close}
      busy={busy}
    >
      <form
        className="rules-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await save({ name, enabled });
            close();
          } catch (e) {
            setError(e instanceof Error ? e.message : "No se guardó el grupo");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Nombre del grupo
          <input
            autoFocus
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <div className="rules-checks">
          <label>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />{" "}
            Grupo activado
          </label>
        </div>
        <p className="rules-help">
          Desactivar un grupo excluye todas sus reglas sin cambiar sus
          interruptores individuales.
        </p>
        {error && (
          <div className="notice error" role="alert">
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
            Guardar grupo
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
