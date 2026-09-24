from dataclasses import dataclass
from pathlib import Path
import csv

@dataclass(frozen=True)
class Segment:
    path: Path
    start: float
    end: float

class CircularBuffer:
    """Only completed segments enter the index. Consumers copy before pruning."""
    def __init__(self, directory: Path, seconds: float):
        self.directory = directory
        self.seconds = seconds
        self.segments: list[Segment] = []
        self.latest = 0.0

    def refresh(self) -> list[Segment]:
        manifest = self.directory / 'segments.csv'
        if not manifest.exists():
            return []
        previous = {s.path.name for s in self.segments}
        rows = []
        for row in csv.reader(manifest.read_text().splitlines()):
            try:
                name, start, end = row
                path = self.directory / Path(name).name
                if path.exists():
                    rows.append(Segment(path, float(start), float(end)))
            except (ValueError, OSError):
                continue
        self.segments = rows
        self.latest = max((s.end for s in rows), default=self.latest)
        return [s for s in rows if s.path.name not in previous]

    def prune(self):
        cutoff = self.latest - self.seconds
        keep = []
        for segment in self.segments:
            if segment.end <= cutoff:
                try:
                    segment.path.unlink(missing_ok=True)
                except PermissionError:
                    keep.append(segment)
            else:
                keep.append(segment)
        self.segments = keep

    @property
    def duration(self):
        return self.latest - self.segments[0].start if self.segments else 0

    def select(self, start: float, end: float):
        return [s for s in self.segments if s.end > start and s.start < end]
