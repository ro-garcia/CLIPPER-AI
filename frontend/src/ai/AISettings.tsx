import { useEffect, useState } from 'react';
import { api } from '../api';
import type { AIConfig, AIStatistics, AIStatus } from './types';
import { scoreNames } from './types';

export function AISettings() {
  const [config,setConfig]=useState<AIConfig|null>(null),[models,setModels]=useState<string[]>([]);
  const [status,setStatus]=useState<AIStatus|null>(null),[stats,setStats]=useState<AIStatistics|null>(null);
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const load=()=>Promise.all([api<AIConfig>('/ai/settings'),api<{name:string}[]>('/ai/models'),api<AIStatus>('/ai/status'),api<AIStatistics>('/ai/statistics')])
    .then(([saved,installed,current,metrics])=>{setConfig(saved);setModels(installed.map(row=>row.name));setStatus(current);setStats(metrics);})
    .catch(error=>setMessage(error instanceof Error?error.message:'No se pudo cargar AI.'));
  useEffect(()=>{void load();},[]);
  async function work(test=false) {
    if(!config)return; setBusy(true);setMessage('');
    try {if(test){const result=await api<{message:string;latency_ms:number}>('/ai/settings/test',config);setMessage(`${result.message} Latencia: ${result.latency_ms} ms.`);}
      else {setConfig(await api<AIConfig>('/ai/settings',config,'PUT'));setMessage('Configuración guardada.');await load();}}
    catch(error){setMessage(error instanceof Error?error.message:'No se pudo completar.');}finally{setBusy(false);}
  }
  if(!config)return <p role="status">{message||'Cargando configuración de IA…'}</p>;
  const update=(key:keyof AIConfig,value:unknown)=>setConfig({...config,[key]:value});
  const fields:[keyof AIConfig,string,number,number,number][]=[
    ['pre_context_seconds','Contexto anterior inicial (s)',0,120,1],['max_pre_context_seconds','Contexto anterior máximo (s)',0,180,1],
    ['post_context_seconds','Contexto posterior (s)',0,60,1],['max_context_chars','Máximo de caracteres',1000,30000,100],
    ['temperature','Temperatura',0,1,.05],['timeout_seconds','Tiempo límite por intento (s)',5,300,5],
    ['max_retries','Reintentos',0,3,1],['per_stream_limit','Máximo por transmisión',1,1000,1],
    ['medium_threshold','Inicio de MEDIUM',0,10,.1],['good_threshold','Inicio de GOOD',0,10,.1],
    ['high_potential_threshold','Inicio de HIGH POTENTIAL',0,10,.1],
    ['review_threshold','Umbral para revisar',0,10,.1],['create_clip_threshold','Umbral para recomendar clip',0,10,.1],
  ];
  return <div className="ai-settings panel"><div><span className="eyebrow">AI MOMENT SCORING · LOCAL</span><h2>Prioriza momentos sin salir de tu equipo.</h2>
    <p>Ollama evalúa candidatos de fase 2. El score es cualitativo: no predice vistas ni crea clips automáticamente.</p></div>
    <div className="ai-status-grid"><span>Procesamiento <b>LOCAL</b></span><span>Estado <b>{status?.status||'OFFLINE'}</b></span><span>Cola <b>{status?.queued||0}</b></span><span>Activo <b>{status?.active_count||0}</b></span><span>Completadas <b>{status?.completed||0}</b></span><span>Fallidas <b>{status?.failed||0}</b></span></div>
    <div className="ai-toggles"><label><input type="checkbox" checked={config.enabled} onChange={event=>update('enabled',event.target.checked)}/>Activar evaluación con IA</label>
      <label>Modo de evaluación<select value={config.evaluation_mode} onChange={event=>update('evaluation_mode',event.target.value)}><option value="MANUAL">Manual</option><option value="AUTOMATIC">Automático</option></select></label></div>
    <div className="ai-form-grid"><label>Proveedor<select value={config.provider} disabled><option value="ollama">Ollama · Local</option></select></label>
      <label>Endpoint<input value={config.endpoint} onChange={event=>update('endpoint',event.target.value)}/></label>
      <label>Modelo<input list="ollama-models" value={config.model} placeholder="Selecciona un modelo instalado" onChange={event=>update('model',event.target.value)}/><datalist id="ollama-models">{models.map(name=><option key={name} value={name}/>)}</datalist></label>
      <label>Evaluaciones simultáneas<input type="number" value={config.max_concurrent} readOnly/><small>Una a la vez para que Whisper y la captura mantengan prioridad.</small></label>
      {fields.map(([key,label,min,max,step])=><label key={key}>{label}<input type="number" min={min} max={max} step={step} value={Number(config[key])} onChange={event=>update(key,Number(event.target.value))}/></label>)}</div>
    <details><summary>Pesos de la nota final</summary><p>Los siete criterios deben sumar 100%. Dependencia de contexto y completitud se muestran aparte.</p><div className="ai-form-grid">{Object.entries(config.weights).map(([key,value])=><label key={key}>{scoreNames[key as keyof typeof scoreNames]} (%)<input type="number" min={0} max={100} step={1} value={Math.round(value*100)} onChange={event=>update('weights',{...config.weights,[key]:Number(event.target.value)/100})}/></label>)}</div></details>
    <section className="ai-statistics"><h3>Estadísticas de IA</h3>{stats&&<div>{[['Candidatos',stats.candidates],['Evaluados',stats.evaluated],['High Potential',stats.high_potential],['Good',stats.good],['Medium',stats.medium],['Low',stats.low],['Fallidos',stats.failed],['Promedio',stats.average_score===null?'—':`${stats.average_score}/10`],['Latencia media',stats.average_latency_ms===null?'—':`${(stats.average_latency_ms/1000).toFixed(1)} s`]].map(([label,value])=><span key={String(label)}>{label}<b>{value}</b></span>)}</div>}</section>
    <p>La transcripción se procesa en este dispositivo. Los trabajos guardan modelo, versión del evaluador y configuración. La creación de clips sigue siendo manual.</p>
    {message&&<div className="notice" role="status">{message}</div>}<div className="ai-actions"><button className="secondary" disabled={busy} onClick={()=>void work(true)}>Probar conexión</button><button className="primary" disabled={busy} onClick={()=>void work()}>{busy?'Procesando…':'Guardar configuración'}</button></div>
  </div>;
}
