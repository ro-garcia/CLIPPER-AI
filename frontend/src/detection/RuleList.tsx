import { Pencil, Power, Trash2, SlidersHorizontal } from "lucide-react";
import { Badge, Empty } from "../components";
import { labels, type Rule, type Configuration } from "./types";
export function RuleList({
  rules,
  config,
  busy,
  edit,
  toggle,
  remove,
}: {
  rules: Rule[];
  config: Configuration;
  busy: boolean;
  edit: (rule: Rule) => void;
  toggle: (rule: Rule) => void;
  remove: (rule: Rule) => void;
}) {
  if (!rules.length)
    return (
      <Empty
        icon={<SlidersHorizontal />}
        title={
          config.rules.length
            ? "No hay coincidencias"
            : "Tu diccionario empieza contigo"
        }
        description={
          config.rules.length
            ? "Prueba otro texto o filtro."
            : "Agrega una regla o importa una configuración JSON. El detector no incluye frases ocultas."
        }
      />
    );
  return (
    <div className="rules-list">
      {rules.map((rule) => (
        <article className="rule-row" key={rule.id}>
          <div className="rule-main">
            <div className="rule-title">
              <strong>{rule.name}</strong>
              <Badge
                tone={
                  config.active_rule_ids.includes(rule.id) ? "green" : "muted"
                }
              >
                {config.active_rule_ids.includes(rule.id)
                  ? "EFECTIVA"
                  : rule.enabled
                    ? "FUERA DEL PERFIL / GRUPO"
                    : "DESACTIVADA"}
              </Badge>
            </div>
            <p className="rule-pattern">“{rule.pattern}”</p>
            <div className="rule-tags">
              <span>{labels[rule.rule_type]}</span>
              <span>{labels[rule.match_type]}</span>
              <span>
                {rule.language === "*"
                  ? "Todos los idiomas"
                  : rule.language.toUpperCase()}
              </span>
              {rule.category && <span>{rule.category}</span>}
              {rule.group_id && (
                <span>
                  {
                    config.groups.find((group) => group.id === rule.group_id)
                      ?.name
                  }
                </span>
              )}
              {rule.case_sensitive && <span>Aa</span>}
            </div>
          </div>
          <div className="rule-side">
            <strong className={rule.weight < 0 ? "weight negative" : "weight"}>
              {rule.weight >= 0 ? "+" : ""}
              {rule.weight.toFixed(2)}
            </strong>
            <div className="rule-actions">
              <button
                className="icon-button"
                disabled={busy}
                onClick={() => edit(rule)}
                title={`Editar ${rule.name}`}
                aria-label={`Editar ${rule.name}`}
              >
                <Pencil size={15} />
              </button>
              <button
                className="icon-button"
                disabled={busy}
                onClick={() => toggle(rule)}
                title={rule.enabled ? "Desactivar regla" : "Activar regla"}
                aria-label={`${rule.enabled ? "Desactivar" : "Activar"} ${rule.name}`}
              >
                <Power size={15} />
              </button>
              <button
                className="icon-button danger"
                disabled={busy}
                onClick={() => remove(rule)}
                title="Eliminar regla"
                aria-label={`Eliminar ${rule.name}`}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
