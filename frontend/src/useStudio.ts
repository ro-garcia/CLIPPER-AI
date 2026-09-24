import { useEffect, useState } from "react";
import { api } from "./api";
import type { Clip, PublicationJob, PublishingStatus, RenderStatus, Resources, SocialAccount, StreamState, System, Transcript } from "./types";
import type { Evaluation } from "./detection/types";
import type { Moment, AIEvaluation, AIStatus, AIStatistics, RankingMoment } from './ai/types';
const empty: StreamState = {
  state: "idle",
  error: "",
  stream_id: null,
  info: null,
  elapsed: 0,
  buffer_seconds: 0,
  buffer_capacity: 600,
  transcription_status: "not_loaded",
  transcription_error: "",
  transcription_queue: 0,
};
export function useStudio() {
  const [clipTiming, setClipTiming] = useState({ before_seconds: 30, after_seconds: 15 });
  const [streams, setStreams] = useState<StreamState[]>([]);
  const [selectedStreamId, selectStream] = useState<string | null>(null);
  const [transcriptsByStream, setTranscriptsByStream] = useState<Record<string, Transcript[]>>({});
  const [detectionByStream, setDetectionByStream] = useState<Record<string, Evaluation>>({});
  const [moments,setMoments]=useState<Moment[]>([]);
  const [evaluations,setEvaluations]=useState<AIEvaluation[]>([]);
  const [ai,setAI]=useState<AIStatus|null>(null);
  const [aiStatistics,setAIStatistics]=useState<AIStatistics|null>(null);
  const [aiRanking,setAIRanking]=useState<RankingMoment[]>([]);
  const [render,setRender]=useState<RenderStatus|null>(null);
  const [publishing,setPublishing]=useState<PublishingStatus|null>(null);
  const [publications,setPublications]=useState<PublicationJob[]>([]);
  const [socialAccounts,setSocialAccounts]=useState<SocialAccount[]>([]);
  const [detection, setDetection] = useState<Evaluation | null>(null);
  const [stream, setStream] = useState(empty),
    [clips, setClips] = useState<Clip[]>([]),
    [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [system, setSystem] = useState<System | null>(null),
    [resources, setResources] = useState<Resources | null>(null),
    [connected, setConnected] = useState(false);
  useEffect(() => {
    let disposed = false;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      socket = new WebSocket("ws://127.0.0.1:8000/ws/live");
      socket.onopen = () => setConnected(true);
      socket.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type) {
          if(data.type.startsWith('ai_evaluation_')) setEvaluations(previous=>[data.data,...previous.filter(row=>row.id!==data.data.id)].sort((a,b)=>b.created_at.localeCompare(a.created_at)));
          if(data.type.startsWith('render_')) setClips(previous=>[data.data,...previous.filter(row=>row.id!==data.data.id)]);
          if(data.type.startsWith('publication_')) setPublications(previous=>[data.data,...previous.filter(row=>row.id!==data.data.id)]);
          return;
        }
        setMoments(data.moments??[]);
        setEvaluations(data.evaluations??[]);
        setAI(data.ai??null);
        setAIStatistics(data.ai_statistics??null);
        setAIRanking(data.ai_ranking??[]);
        setRender(data.render??null);
        setPublishing(data.publishing??null);
        setPublications(data.publications??[]);
        setSocialAccounts(data.social_accounts??[]);
        setStream(data.stream);
        if (data.clip_timing) setClipTiming(data.clip_timing);
        setStreams(data.streams ?? []);
        setTranscriptsByStream(data.transcripts_by_stream ?? {});
        setDetectionByStream(data.detection_by_stream ?? {});
        setClips(data.clips);
        setTranscripts(data.transcripts);
        setDetection(data.detection ?? null);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) retry = setTimeout(connect, 2500);
      };
      socket.onerror = () => socket.close();
    };
    const poll = () =>
      Promise.all([
        api<System>("/system/status"),
        api<Resources>("/system/resources"),
      ])
        .then(([s, r]) => {
          if (!disposed) {
            setSystem(s);
            setResources(r);
          }
        })
        .catch(() => {
          if (!disposed) setSystem(null);
        });
    connect();
    void poll();
    const timer = setInterval(poll, 8000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearInterval(timer);
      socket.close();
    };
  }, []);
  const selectedStream = streams.find(s => s.stream_id === selectedStreamId) ?? stream;
  return {
    streams, selectedStreamId, selectStream, clipTiming, setClipTiming,
    moments, evaluations, ai, aiStatistics, aiRanking, render, publishing, publications, socialAccounts,
    stream: selectedStream,
    clips,
    transcripts: selectedStream.stream_id ? transcriptsByStream[selectedStream.stream_id] ?? [] : transcripts,
    system,
    resources,
    connected,
    detection: selectedStream.stream_id ? detectionByStream[selectedStream.stream_id] ?? null : detection,
  };
}
