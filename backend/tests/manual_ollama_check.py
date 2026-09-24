"""Opt-in local integration check. No downloads, cloud requests or production DB writes."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

production=backend_root/'storage'
with sqlite3.connect(f'file:{(production/"liveclip.db").as_posix()}?mode=ro',uri=True) as db:
    stream=db.execute('select id,title,url from streams order by created_at desc limit 1').fetchone()
    rows=db.execute('select start,end,text from transcriptions where stream_id=? order by start',(stream[0],)).fetchall()
os.environ['STORAGE_DIR']=tempfile.mkdtemp(prefix='liveclip-local-ai-')
from app.database import Base,engine,Session,Stream,Transcript,serialize
from app.detection.cache import Rule,RulesSnapshot,normalize
from app.moments.detector import detect
from app.moments.models import Moment
from app.moments.service import moments,get_moment
from app.services.buffer import CircularBuffer
from app.ai.service import AIService,evaluations
from app.ai.schemas import AISettings

async def main():
    Base.metadata.create_all(engine);moments.recover()
    parts=[{'start':r[0],'end':r[1],'text':r[2]} for r in rows]
    found=None
    for index in range(5,len(parts)):
        fragment=parts[max(0,index-15):index+1]
        pattern=fragment[-1]['text'].split()[0]
        rule=Rule('local-test','Integration test',pattern,'KEYWORD','',.5,'*','CONTAINS',False,normalize(pattern))
        found=detect(fragment,'es',RulesSnapshot(rules=(rule,)))
        if found:break
    if not found:raise RuntimeError('No suitable recorded candidate for this test')
    with Session.begin() as db:
        db.add(Stream(id=stream[0],title=stream[1],url=stream[2]))
        for part in parts:db.add(Transcript(stream_id=stream[0],**part))
        db.add(Moment(id='integration',stream_id=stream[0],start=found.start,end=found.end,
            transcript_excerpt=found.text,language='es',moment_type=found.kind,detection_confidence=found.confidence,
            detection_reasons=found.reasons,rule_revision=1))
    buffer=CircularBuffer(production/'buffer'/stream[0],600);buffer.refresh()
    moments.preserve('integration',buffer)
    if moments.tasks:await asyncio.gather(*moments.tasks)
    preview=get_moment('integration')['media_status']
    clip=await moments.create_clip('integration') if preview=='READY' else None
    print(json.dumps({'stage':'candidate_preview_clip','confidence':found.confidence,'preview':preview,
        'clip_status':clip['status'] if clip else None,'start':found.start,'end':found.end}),flush=True)
    service=AIService();service.config=AISettings(enabled=True,model='gemma4:26b',timeout_seconds=300,max_retries=0)
    job=service.enqueue('integration')
    start=time.monotonic();await service.run(job['id'])
    evaluation=evaluations('integration')[0]
    report={'status':evaluation['status'],'result':evaluation['result'],'error':evaluation['error_message'],
        'latency_seconds':round(time.monotonic()-start,2),'model':evaluation['model'],
        'preview':preview,'clip_status':clip['status'] if clip else None}
    output=Path(__file__).resolve().parents[2]/'docs'/'local-ai-check.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

asyncio.run(main())
