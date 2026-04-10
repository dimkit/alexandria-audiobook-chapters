import os
import shutil
import subprocess


_FFMPEG_EXE = None


def get_ffmpeg_exe():
    global _FFMPEG_EXE
    if _FFMPEG_EXE:
        return _FFMPEG_EXE

    try:
        import imageio_ffmpeg

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and os.path.exists(candidate):
            _FFMPEG_EXE = candidate
            return _FFMPEG_EXE
    except Exception:
        pass

    _FFMPEG_EXE = shutil.which("ffmpeg") or "ffmpeg"
    return _FFMPEG_EXE


def get_ffprobe_exe():
    return shutil.which("ffprobe") or "ffprobe"


def configure_pydub(AudioSegment):
    ffmpeg_exe = get_ffmpeg_exe()
    AudioSegment.converter = ffmpeg_exe
    AudioSegment.ffmpeg = ffmpeg_exe
    ffprobe_exe = get_ffprobe_exe()
    if ffprobe_exe:
        AudioSegment.ffprobe = ffprobe_exe
    try:
        import pydub.audio_segment as audio_segment

        original_mediainfo_json = audio_segment.mediainfo_json

        def safe_mediainfo_json(*args, **kwargs):
            try:
                return original_mediainfo_json(*args, **kwargs)
            except Exception:
                return {}

        audio_segment.mediainfo_json = safe_mediainfo_json
    except Exception:
        pass
    return ffmpeg_exe


def has_mp3_encoder(ffmpeg_exe=None):
    cmd = [ffmpeg_exe or get_ffmpeg_exe(), "-hide_banner", "-encoders"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return False
    encoders = f"{result.stdout}\n{result.stderr}".lower()
    return result.returncode == 0 and ("libmp3lame" in encoders or " mp3" in encoders)
