import { useRef, useState } from "react";
import {
  Download,
  Upload,
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../api";
import { Badge } from "../components";
import { useRules, rulesChanged } from "./useRules";
import { RuleEditor } from "./RuleEditor";
import { GroupEditor } from "./GroupEditor";
import { ProfileEditor } from "./ProfileEditor";
import { RuleList } from "./RuleList";
import { GroupList, ProfileList } from "./ConfigurationLists";
import { ProfileSelector } from "./ProfileSelector";
import { RuleTester } from "./RuleTester";
import { Dialog } from "./Dialog";
import {
  ruleTypes,
  labels,
  type Rule,
  type Group,
  type Profile,
} from "./types";
type Editor =
  | { kind: "rule"; item: Rule | null }
  | { kind: "group"; item: Group | null }
  | { kind: "profile"; item: Profile | null };
export function RulesManager() {
  const { config, error, reload } = useRules(),
    [tab, setTab] = useState("rules"),
    [search, setSearch] = useState(""),
    [type, setType] = useState(""),
    [group, setGroup] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [failure, setFailure] = useState("");
  const [deletion, setDeletion] = useState<{
      path: string;
      name: string;
      kind: string;
    } | null>(null),
    [incoming, setIncoming] = useState<{ name: string; data: unknown } | null>(
      null,
    );
  const fileInput = useRef<HTMLInputElement>(null);
  async function persist(path: string, payload?: unknown, method?: string) {
    await api(path, payload, method);
    await reload();
    rulesChanged();
    setMessage("Configuración guardada. La caché ya está actualizada.");
    setFailure("");
  }
  async function operate(work: () => Promise<void>) {
    setBusy(true);
    setFailure("");
    try {
      await work();
    } catch (e) {
      setFailure(
        e instanceof Error ? e.message : "No se pudo completar la operación",
      );
    } finally {
      setBusy(false);
    }
  }
  async function exportRules() {
    const bundle = await api("/moment-rules/export");
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "liveclip_rules.json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (!config)
    return (
      <section className="panel">
        <div className="panel-heading">
          <h3>Detection Rules</h3>
        </div>
        {error ? (
          <div className="notice error">
            {error}
            <button onClick={() => void reload()}>Reintentar</button>
          </div>
        ) : (
          <div className="rules-loading skeleton" />
        )}
      </section>
    );
  const filtered = config.rules.filter(
    (rule) =>
      (!type || rule.rule_type === type) &&
      (!group || rule.group_id === group) &&
      `${rule.name} ${rule.pattern} ${rule.category}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <div className="detection-manager">
      <section className="rules-intro">
        <div>
          <span className="eyebrow">MOMENT DETECTION / CONFIGURATION</span>
          <h2>Tu contenido. Tus señales.</h2>
          <p>
            Define qué merece atención. Ajusta el diccionario mientras el
            estudio sigue trabajando.
          </p>
        </div>
        <Badge tone="violet">
          {config.active_rule_ids.length} REGLAS EFECTIVAS
        </Badge>
      </section>
      <ProfileSelector />
      <section className="panel">
        <div className="rules-toolbar">
          <div
            className="rules-tabs"
            role="tablist"
            aria-label="Configuración de detección"
          >
            {[
              ["rules", "Reglas"],
              ["groups", "Grupos"],
              ["profiles", "Perfiles"],
              ["test", "Probar reglas"],
            ].map(([key, label]) => (
              <button
                role="tab"
                aria-selected={tab === key}
                className={tab === key ? "selected" : ""}
                key={key}
                onClick={() => setTab(key)}
              >
                {label}
                {key !== "test" && (
                  <small>
                    {config[key as "rules" | "groups" | "profiles"].length}
                  </small>
                )}
              </button>
            ))}
          </div>
          <div className="rules-toolbar-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => void operate(exportRules)}
            >
              <Download size={14} /> Exportar
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              <Upload size={14} /> Importar
            </button>
            {tab !== "test" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  setEditor({
                    kind:
                      tab === "rules"
                        ? "rule"
                        : tab === "groups"
                          ? "group"
                          : "profile",
                    item: null,
                  } as Editor)
                }
              >
                <Plus size={15} />{" "}
                {tab === "rules"
                  ? "Agregar regla"
                  : tab === "groups"
                    ? "Agregar grupo"
                    : "Agregar perfil"}
              </button>
            )}
          </div>
        </div>
        <input
          type="file"
          ref={fileInput}
          accept="application/json,.json"
          hidden
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            setFailure("");
            try {
              if (file.size > 1_000_000)
                throw new Error("El JSON debe ocupar menos de 1 MB.");
              const data = JSON.parse(await file.text());
              setIncoming({ name: file.name, data });
            } catch (e) {
              setFailure(e instanceof Error ? e.message : "JSON inválido");
            }
          }}
        />
        {(error || failure) && (
          <div className="notice error" role="alert">
            {failure || error}
          </div>
        )}
        {message && (
          <div className="rules-feedback" role="status">
            {message}
            <button aria-label="Cerrar mensaje" onClick={() => setMessage("")}>
              ×
            </button>
          </div>
        )}
        {tab === "rules" && (
          <>
            <div className="rules-filters">
              <label className="rule-search">
                <Search size={15} />
                <input
                  aria-label="Buscar reglas"
                  placeholder="Buscar por nombre, frase o categoría…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <select
                aria-label="Filtrar por tipo"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                <option value="">Todos los tipos</option>
                {ruleTypes.map((type) => (
                  <option key={type} value={type}>
                    {labels[type]}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filtrar por grupo"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              >
                <option value="">Todos los grupos</option>
                {config.groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
            <RuleList
              rules={filtered}
              config={config}
              busy={busy}
              edit={(item) => setEditor({ kind: "rule", item })}
              toggle={(rule) =>
                void operate(() =>
                  persist(
                    `/moment-rules/${rule.id}/${rule.enabled ? "disable" : "enable"}`,
                    {},
                  ),
                )
              }
              remove={(rule) =>
                setDeletion({
                  path: `/moment-rules/${rule.id}`,
                  name: rule.name,
                  kind: "regla",
                })
              }
            />
          </>
        )}
        {tab === "groups" && (
          <GroupList
            config={config}
            busy={busy}
            edit={(item) => setEditor({ kind: "group", item })}
            toggle={(g) =>
              void operate(() =>
                persist(
                  `/moment-rules/groups/${g.id}`,
                  { name: g.name, enabled: !g.enabled },
                  "PUT",
                ),
              )
            }
            remove={(g) =>
              setDeletion({
                path: `/moment-rules/groups/${g.id}`,
                name: g.name,
                kind: "grupo",
              })
            }
          />
        )}
        {tab === "profiles" && (
          <ProfileList
            config={config}
            busy={busy}
            edit={(item) => setEditor({ kind: "profile", item })}
            activate={(p) =>
              void operate(() =>
                persist("/moment-profiles/active", { profile_id: p.id }),
              )
            }
            remove={(p) =>
              setDeletion({
                path: `/moment-profiles/${p.id}`,
                name: p.name,
                kind: "perfil",
              })
            }
          />
        )}
        {tab === "test" && <RuleTester revision={config.revision} />}
        <footer className="rules-footer">
          <SlidersHorizontal size={13} /> Cambios aplicados sin reiniciar ·
          revisión {config.revision}
          <span>Señales lingüísticas ≠ clip automático</span>
        </footer>
      </section>
      {editor?.kind === "rule" && (
        <RuleEditor
          rule={editor.item}
          groups={config.groups}
          close={() => setEditor(null)}
          save={(value) =>
            persist(
              editor.item ? `/moment-rules/${editor.item.id}` : "/moment-rules",
              value,
              editor.item ? "PUT" : "POST",
            )
          }
        />
      )}
      {editor?.kind === "group" && (
        <GroupEditor
          group={editor.item}
          close={() => setEditor(null)}
          save={(value) =>
            persist(
              editor.item
                ? `/moment-rules/groups/${editor.item.id}`
                : "/moment-rules/groups",
              value,
              editor.item ? "PUT" : "POST",
            )
          }
        />
      )}
      {editor?.kind === "profile" && (
        <ProfileEditor
          profile={editor.item}
          config={config}
          close={() => setEditor(null)}
          save={(value) =>
            persist(
              editor.item
                ? `/moment-profiles/${editor.item.id}`
                : "/moment-profiles",
              value,
              editor.item ? "PUT" : "POST",
            )
          }
        />
      )}
      {deletion && (
        <Dialog
          title={`Eliminar ${deletion.kind}`}
          close={() => setDeletion(null)}
          busy={busy}
        >
          <div className="rules-form">
            <p>¿Eliminar “{deletion.name}”?</p>
            <p className="rules-help">
              {deletion.kind === "grupo"
                ? "Sus reglas se conservan sin grupo y quedan desactivadas. Se retira el grupo de los perfiles."
                : "Se retira de la configuración. Esta acción no se puede deshacer."}
            </p>
            {failure && <div className="notice error">{failure}</div>}
            <footer>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => setDeletion(null)}
              >
                Cancelar
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  void operate(async () => {
                    await persist(deletion.path, undefined, "DELETE");
                    setDeletion(null);
                  })
                }
              >
                Eliminar
              </button>
            </footer>
          </div>
        </Dialog>
      )}
      {incoming && (
        <Dialog
          title="Importar configuración JSON"
          close={() => setIncoming(null)}
          busy={busy}
        >
          <div className="rules-form">
            <strong>{incoming.name}</strong>
            <p className="rules-help">
              Se validará el archivo completo antes de guardar. Se agregan
              copias nuevas de sus reglas, grupos y perfiles; no se reemplaza
              nada y se mantiene el perfil seleccionado. Las reglas habilitadas
              pueden empezar a aportar señales inmediatamente.
            </p>
            {failure && (
              <div className="notice error" role="alert">
                {failure}
              </div>
            )}
            <footer>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => setIncoming(null)}
              >
                Cancelar
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  void operate(async () => {
                    await persist("/moment-rules/import", incoming.data);
                    setIncoming(null);
                  })
                }
              >
                Importar configuración
              </button>
            </footer>
          </div>
        </Dialog>
      )}
    </div>
  );
}
