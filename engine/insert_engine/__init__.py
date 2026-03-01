"""Vclip - Insert Engine: sistema de inserts parametrizados.

Suporta:
- Insert fixo no início de cada corte
- Insert overlay animado (fade in/out)
- Insert como lower-third
- Parâmetros: duração, opacidade, blend, posição, escala
"""

import subprocess
from pathlib import Path
from engine.config import EXPORT_CRF, EXPORT_PRESET


class InsertEngine:
    """Aplica inserts (layoutcorte) nos vídeos."""

    def __init__(
        self,
        insert_path: str = "assets/layoutcorte.png",
        mode: str = "overlay",          # "overlay" | "prepend" | "lower_third"
        duration: float = 0.0,           # 0 = full clip duration
        opacity: float = 1.0,
        position: str = "cover",         # "cover" | "top" | "bottom" | "center"
        scale: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ):
        self.insert_path = insert_path
        self.mode = mode
        self.duration = duration
        self.opacity = opacity
        self.position = position
        self.scale = scale
        self.fade_in = fade_in
        self.fade_out = fade_out

    def apply(self, input_video: str, output_path: str, clip_duration: float = 0) -> str:
        p = Path(self.insert_path)
        if not p.is_file():
            print(f"[Insert] Arquivo não encontrado: {self.insert_path}")
            return input_video

        is_video = p.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv")

        if self.mode == "prepend" and is_video:
            return self._prepend(input_video, output_path)
        else:
            return self._overlay(input_video, output_path, clip_duration)

    def _overlay(self, input_video: str, output_path: str, clip_dur: float) -> str:
        """Aplica como overlay sobre o vídeo."""
        dur = self.duration if self.duration > 0 else clip_dur
        x, y = self._calc_pos()

        parts = []
        # Scale insert
        if self.scale != 1.0:
            parts.append(f"scale=iw*{self.scale}:ih*{self.scale}")
        # Opacity
        if self.opacity < 1.0:
            parts.append(f"format=rgba,colorchannelmixer=aa={self.opacity}")
        # Fade
        if self.fade_in > 0:
            parts.append(f"fade=in:st=0:d={self.fade_in}:alpha=1")
        if self.fade_out > 0 and dur > 0:
            parts.append(f"fade=out:st={max(0, dur - self.fade_out)}:d={self.fade_out}:alpha=1")

        filter_str = ",".join(parts) if parts else "null"

        if dur > 0 and dur < clip_dur:
            fc = f"[1:v]{filter_str}[ovr];[0:v][ovr]overlay={x}:{y}:enable='between(t,0,{dur})'"
        else:
            fc = f"[1:v]{filter_str}[ovr];[0:v][ovr]overlay={x}:{y}"

        cmd = [
            "ffmpeg", "-y", "-i", input_video, "-i", self.insert_path,
            "-filter_complex", fc,
            "-c:v", "libx264", "-crf", str(EXPORT_CRF),
            "-preset", EXPORT_PRESET, "-c:a", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"[Insert] Erro: {result.stderr[-200:]}")
            return input_video
        return output_path

    def _prepend(self, input_video: str, output_path: str) -> str:
        """Adiciona insert como vídeo antes do clip."""
        concat_file = Path(output_path).with_suffix(".txt")
        concat_file.write_text(
            f"file '{self.insert_path}'\nfile '{input_video}'\n",
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c", "copy", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        concat_file.unlink(missing_ok=True)
        if result.returncode != 0:
            return input_video
        return output_path

    def _calc_pos(self):
        pos = {
            "cover": ("0", "0"),
            "top": ("(W-w)/2", "0"),
            "bottom": ("(W-w)/2", "H-h"),
            "center": ("(W-w)/2", "(H-h)/2"),
        }
        return pos.get(self.position, ("0", "0"))
