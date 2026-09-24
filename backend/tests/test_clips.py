import asyncio
from app.database import Base, engine, Session, Clip
from app.services.buffer import CircularBuffer
from app.services.clips import ClipGenerator

def test_clip_pins_history_and_fails_cleanly_on_interruption(tmp_path):
    Base.metadata.create_all(engine)
    (tmp_path / 'segment_00000000.ts').write_bytes(b'previous video')
    (tmp_path / 'segment_00000001.ts').write_bytes(b'recent video')
    (tmp_path / 'segments.csv').write_text('segment_00000000.ts,0,20\nsegment_00000001.ts,20,35\n')
    buffer = CircularBuffer(tmp_path, 30)
    buffer.refresh()
    generator = ClipGenerator()
    result = generator.create('unit-stream', 'Test clip', buffer, anchor=37)
    job = generator.pending[result['id']]
    assert job['start'] == 7 and job['end'] == 52
    assert len(job['segments']) == 2
    buffer.latest = 70
    buffer.prune()
    assert not (tmp_path / 'segment_00000000.ts').exists()
    assert (job['directory'] / 'segment_00000000.ts').read_bytes() == b'previous video'
    generator.fail_pending()
    assert not list(job['directory'].glob('*.ts'))
    with Session() as db:
        row = db.get(Clip, result['id'])
        assert row.status == 'error'
        assert '15 segundos' in row.error
