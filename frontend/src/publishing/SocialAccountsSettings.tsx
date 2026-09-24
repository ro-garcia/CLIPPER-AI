import { useEffect, useState } from "react";
import { Link2, ShieldCheck, Unplug } from "lucide-react";
import { api } from "../api";
import type { PlatformCapability, PublishingConfig, SocialAccount, SocialPlatform } from "../types";

const names: Record<SocialPlatform, string> = { youtube: "YouTube Shorts", tiktok: "TikTok", instagram: "Instagram Reels", facebook: "Facebook Reels" };

export function SocialAccountsSettings() {
  const [config,setConfig]=useState<PublishingConfig|null>(null),[accounts,setAccounts]=useState<SocialAccount[]>([]),[caps,setCaps]=useState<PlatformCapability[]>([]),[message,setMessage]=useState("");
  const load=()=>Promise.all([api<PublishingConfig>("/publishing/settings"),api<SocialAccount[]>("/publishing/accounts"),api<PlatformCapability[]>("/publishing/capabilities")])
    .then(([settings,rows,capabilities])=>{setConfig(settings);setAccounts(rows);setCaps(capabilities);}).catch((error)=>setMessage(error.message));
  useEffect(()=>{void load();},[]);
  async function connect(platform: SocialPlatform) {
    try { const result=await api<{authorization_url?:string}>(`/publishing/accounts/${platform}/connect`,{});
      if(result.authorization_url) window.open(result.authorization_url,"_blank","noopener,noreferrer");
      setMessage(result.authorization_url?"Completa la autorización en el navegador oficial.":"Cuenta mock conectada para pruebas seguras."); await load();
    } catch(error){setMessage(error instanceof Error?error.message:"No se pudo conectar.");}
  }
  async function disconnect(id:string){try{await api(`/publishing/accounts/${id}`,{},"DELETE");await load();}catch(error){setMessage(error instanceof Error?error.message:"No se pudo desconectar.");}}
  async function save(){if(!config)return;try{setConfig(await api<PublishingConfig>("/publishing/settings",config,"PUT"));setMessage("Configuración guardada. Reinicia el backend si cambiaste la concurrencia.");await load();}catch(error){setMessage(error instanceof Error?error.message:"No se pudo guardar.");}}
  if(!config)return <section className="panel social-settings">{message||"Cargando Social Publishing…"}</section>;
  return <div className="social-settings">
    <div className="safe-mode-banner"><ShieldCheck size={18}/><div><strong>{config.safe_publish_mode?"SAFE MODE ACTIVO":"PUBLICACIÓN REAL"}</strong><p>{config.safe_publish_mode?"Todos los uploads usan MockSocialPublisher.":"Las acciones enviarán contenido a APIs oficiales."}</p></div></div>
    <section className="panel"><div className="panel-heading"><h3><Link2 size={17}/> Social accounts</h3></div><div className="social-account-list">
      {(["youtube","tiktok","instagram","facebook"] as SocialPlatform[]).map((platform)=>{const capability=caps.find((item)=>item.platform===platform);const rows=accounts.filter((account)=>account.platform===platform);return <article key={platform}>
        <div className={`platform-mark ${platform}`}>{platform[0].toUpperCase()}</div><div><strong>{names[platform]}</strong><p>{capability?.support.replaceAll("_"," ")}{capability?.configuration_required&&` · ${capability.configuration_required}`}</p>
          {rows.map((account)=><small key={account.id}><i className={`dot ${account.status==="CONNECTED"?"green":""}`}/>{account.display_name} · {account.status} · {account.provider_mode.toUpperCase()} <button onClick={()=>void disconnect(account.id)}><Unplug size={11}/> Desconectar</button></small>)}</div>
        {!rows.some((row)=>row.status==="CONNECTED")&&<button className="secondary" onClick={()=>void connect(platform)}>Conectar</button>}
      </article>})}</div></section>
    <section className="panel publishing-config"><div className="panel-heading"><h3>Distribution engine</h3></div>
      <div className="ai-toggles"><label><input type="checkbox" checked={config.social_publishing_enabled} onChange={e=>setConfig({...config,social_publishing_enabled:e.target.checked})}/>Activar Social Publishing</label><label><input type="checkbox" checked={config.safe_publish_mode} onChange={e=>setConfig({...config,safe_publish_mode:e.target.checked,publishing_mode:e.target.checked?"mock":"real"})}/>Safe Publish Mode</label></div>
      <div className="ai-form-grid"><label>Workflow<select value={config.publication_workflow} onChange={e=>setConfig({...config,publication_workflow:e.target.value as PublishingConfig["publication_workflow"]})}><option>MANUAL</option><option>REVIEW</option><option>AUTOMATIC</option></select></label>
        <label>Publicaciones simultáneas<input type="number" min={1} max={4} value={config.max_concurrent_publications} onChange={e=>setConfig({...config,max_concurrent_publications:Number(e.target.value)})}/></label>
        <label>Máximo de intentos<input type="number" min={1} max={5} value={config.max_retry_attempts} onChange={e=>setConfig({...config,max_retry_attempts:Number(e.target.value)})}/></label>
        <label>Programación perdida<select value={config.missed_schedule_policy} onChange={e=>setConfig({...config,missed_schedule_policy:e.target.value as PublishingConfig["missed_schedule_policy"]})}><option>PUBLISH_WHEN_AVAILABLE</option><option>ASK_USER</option><option>CANCEL</option></select></label>
        <label>Privacidad YouTube<select value={config.youtube_privacy_status} onChange={e=>setConfig({...config,youtube_privacy_status:e.target.value as PublishingConfig["youtube_privacy_status"]})}><option value="private">PRIVATE</option><option value="unlisted">UNLISTED</option><option value="public">PUBLIC</option></select></label>
      </div>{message&&<div className="notice">{message}</div>}<div className="ai-actions"><button className="primary" onClick={()=>void save()}>Guardar configuración</button></div>
    </section>
  </div>;
}
