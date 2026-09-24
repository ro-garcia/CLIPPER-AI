import {
  AudioLines,
  ChartNoAxesCombined,
  Clapperboard,
  FolderOpen,
  LayoutDashboard,
  PanelLeftClose,
  Radio,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "./api";
import { Badge } from "./components";
import { useStudio } from "./useStudio";
import type { Clip } from "./types";

const navigation = [
  { name: "Dashboard", icon: LayoutDashboard },
  { name: "Live Monitor", icon: Radio },
  { name: "Moments", icon: Sparkles },
  { name: "Clips", icon: Clapperboard },
  { name: "Library", icon: FolderOpen },
  { name: "Analytics", icon: ChartNoAxesCombined, phase: 9 },
  { name: "Publish", icon: Send },
];
export { navigation };
export function AppSidebar({
  page,
  setPage,
  collapsed,
  setCollapsed,
  clips,
  active,
}: {
  page: string;
  setPage: (page: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  clips: Clip[];
  active: boolean;
}) {
  return (
    <aside className="sidebar">
      <a className="brand" href="#" onClick={(e) => e.preventDefault()}>
        <span className="brand-symbol">
          <AudioLines size={23} />
        </span>
        <span>
          LiveClip <b>AI</b>
          <small>LOCAL PRODUCTION STUDIO</small>
        </span>
      </a>
      <div className="workspace">
        <div className="workspace-avatar">LC</div>
        <div>
          <strong>Mi estudio</strong>
          <small>Workspace local</small>
        </div>
        <Badge>01</Badge>
      </div>
      <span className="nav-label">WORKSPACE</span>
      <nav>
        {navigation.map(({ name, icon: Icon, phase }) => (
          <button
            key={name}
            title={collapsed ? name : undefined}
            className={page === name ? "nav-item active" : "nav-item"}
            onClick={() => setPage(name)}
          >
            <Icon size={18} />
            <span>{name}</span>
            {name === "Clips" && clips.length > 0 ? (
              <small>{clips.length}</small>
            ) : phase ? (
              <span className="phase-mark">Próximamente</span>
            ) : name === "Live Monitor" && active ? (
              <span className="dot red" />
            ) : null}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="local-card">
          <ShieldCheck size={19} />
          <strong>Tu contenido se queda aquí.</strong>
          <p>
            Captura y procesamiento
            <br />
            en tu propio equipo.
          </p>
          <Badge tone="violet">LOCAL STUDIO</Badge>
        </div>
        <button
          className={page === "Settings" ? "nav-item active" : "nav-item"}
          onClick={() => setPage("Settings")}
        >
          <Settings size={18} />
          <span>Settings</span>
        </button>
        <button
          className="nav-item collapse-control"
          onClick={() => setCollapsed(!collapsed)}
          title="Colapsar navegación"
        >
          <PanelLeftClose size={18} />
          <span>Colapsar panel</span>
        </button>
      </div>
    </aside>
  );
}
