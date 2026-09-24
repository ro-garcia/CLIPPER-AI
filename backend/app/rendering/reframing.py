"""Small, extensible FFmpeg composition strategies for vertical output."""
from __future__ import annotations

from pathlib import Path


class ReframingStrategy:
    name = 'CENTER_CROP'

    def video_filter(self, config, subtitle_file: Path | None) -> str:
        width, height = config.output_width, config.output_height
        if config.background_mode == 'CROP':
            base = f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}'
        elif config.background_mode == 'BLUR':
            base = (f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:10[bg];'
                    f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2')
        else:
            base = (f'color=c=black:s={width}x{height}[bg];'
                    f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];'
                    f'[bg][fg]overlay=(W-w)/2:(H-h)/2')
        if not subtitle_file:
            return base + '[v]'
        base += '[base]'
        escaped = subtitle_file.as_posix().replace('\\', '/').replace(':', r'\:').replace("'", r"\'")
        # The ASS filter reads UTF-8 ASS directly; unlike `subtitles`, it has no charenc option.
        return base + f";[base]ass=filename='{escaped}'[v]"


class CenterCrop(ReframingStrategy):
    name = 'CENTER_CROP'


class SmartCrop(CenterCrop):
    """Fallback center crop until a local visual focus provider is configured."""
    name = 'SMART_CROP'


class SubjectTracking(CenterCrop):
    """Extension point. It intentionally falls back instead of blocking a render."""
    name = 'SUBJECT_TRACKING'


def strategy_for(config) -> ReframingStrategy:
    return {'SMART_CROP': SmartCrop(), 'SUBJECT_TRACKING': SubjectTracking()}.get(
        config.reframing_mode, CenterCrop())
