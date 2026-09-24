"""Publish the completed, clearly labelled local integration example for review."""
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
from uuid import uuid4
from app.database import Session
from app.moments.models import Moment
from app.moments.service import ROOT
from app.ai.models import AIEvaluation

folders=sorted(Path(tempfile.gettempdir()).glob('liveclip-local-ai-*'),key=lambda p:p.stat().st_mtime,reverse=True)
source=next(p for p in folders if (p/'moments'/'integration'/'preview.mp4').exists())
with sqlite3.connect(source/'liveclip.db') as connection:
    connection.row_factory=sqlite3.Row
    moment=dict(connection.execute("select * from moments where id='integration'").fetchone())
    evaluation=dict(connection.execute("select * from moment_ai_evaluations where moment_id='integration' and status='EVALUATED' order by created_at desc limit 1").fetchone())
identifier='example-'+uuid4().hex
moment.update(id=identifier,moment_type='PRUEBA DE INTEGRACIÓN',clip_id=None)
moment['detection_reasons']=json.loads(moment['detection_reasons'])+[{'kind':'TEST','description':'Captura anterior real. Regla temporal de prueba, independiente de tus reglas y perfiles.'}]
evaluation.update(id=uuid4().hex,moment_id=identifier)
for key in ('result','settings_snapshot','context_metadata'):
    evaluation[key]=json.loads(evaluation[key]) if evaluation[key] else None
directory=ROOT/identifier;directory.mkdir()
shutil.copy2(source/'moments'/'integration'/'preview.mp4',directory/'preview.mp4')
with Session.begin() as db:
    db.add(Moment(**moment));db.add(AIEvaluation(**evaluation))
print(identifier)
