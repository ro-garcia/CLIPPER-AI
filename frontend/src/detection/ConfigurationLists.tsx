import { Folder, Layers, Pencil, Power, Trash2 } from "lucide-react";
import { Badge, Empty } from "../components";
import type { Configuration, Group, Profile } from "./types";
export function GroupList({
  config,
  busy,
  edit,
  toggle,
  remove,
}: {
  config: Configuration;
  busy: boolean;
  edit: (g: Group) => void;
  toggle: (g: Group) => void;
  remove: (g: Group) => void;
}) {
  if (!config.groups.length)
    return (
      <Empty
        icon={<Folder />}
        title="Organiza tus señales"
        description="Crea grupos para activar o desactivar conjuntos de reglas de una sola vez."
      />
    );
  return (
    <div className="rules-list">
      {config.groups.map((group) => (
        <article className="rule-row" key={group.id}>
          <div className="rule-main">
            <div className="rule-title">
              <strong>{group.name}</strong>
              <Badge tone={group.enabled ? "green" : "muted"}>
                {group.enabled ? "ACTIVADO" : "DESACTIVADO"}
              </Badge>
            </div>
            <p className="rules-help">
              {config.rules.filter((rule) => rule.group_id === group.id).length}{" "}
              reglas en este grupo
            </p>
          </div>
          <div className="rule-actions">
            <button
              disabled={busy}
              title="Editar grupo"
              onClick={() => edit(group)}
            >
              <Pencil size={15} />
            </button>
            <button
              disabled={busy}
              title={group.enabled ? "Desactivar grupo" : "Activar grupo"}
              onClick={() => toggle(group)}
            >
              <Power size={15} />
            </button>
            <button
              disabled={busy}
              title="Eliminar grupo"
              onClick={() => remove(group)}
            >
              <Trash2 size={15} />
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
export function ProfileList({
  config,
  busy,
  edit,
  activate,
  remove,
}: {
  config: Configuration;
  busy: boolean;
  edit: (p: Profile) => void;
  activate: (p: Profile) => void;
  remove: (p: Profile) => void;
}) {
  if (!config.profiles.length)
    return (
      <Empty
        icon={<Layers />}
        title="Un perfil para cada contenido"
        description="Selecciona grupos y reglas para cambiar de configuración sin modificar el motor."
      />
    );
  return (
    <div className="rules-list">
      {config.profiles.map((profile) => (
        <article className="rule-row" key={profile.id}>
          <div className="rule-main">
            <div className="rule-title">
              <strong>{profile.name}</strong>
              {config.active_profile_id === profile.id && (
                <Badge tone="violet">EN USO</Badge>
              )}
            </div>
            <p className="rules-help">
              {profile.group_ids.length} grupos · {profile.rule_ids.length}{" "}
              reglas individuales
            </p>
          </div>
          <div className="rule-actions">
            <button
              disabled={busy || config.active_profile_id === profile.id}
              className="secondary"
              onClick={() => activate(profile)}
            >
              Usar perfil
            </button>
            <button
              disabled={busy}
              title="Editar perfil"
              onClick={() => edit(profile)}
            >
              <Pencil size={15} />
            </button>
            <button
              disabled={busy}
              title="Eliminar perfil"
              onClick={() => remove(profile)}
            >
              <Trash2 size={15} />
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
