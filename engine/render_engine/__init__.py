"""Vclip - Render Engine: renderiza a Timeline em vídeo final.

Lê a estrutura Timeline (keyframes, effects, clips) e gera
o vídeo final usando FFmpeg + OpenCV.
"""

import subprocess
import math
import json
import numpy as np
import cv2
from pathlib import Path

from engine.config import EXPORT_CRF, EXPORT_PRESET


class RenderEngine:
    """Renderiza Timeline para arquivo de vídeo."""

    def __init__(self):
        self.progress_callback = None

    def render(self, timeline_data: dict, output_path: str,
               progress_cb=None) -> str:
        """Renderiza timeline completa para vídeo.

        Args:
            timeline_data: Timeline serializada (dict).
            output_path: Caminho do vídeo de saída.
            progress_cb: Callback(progress_0_to_1).
        """
        self.progress_callback = progress_cb
        from engine.timeline_builder import Timeline
        tl = Timeline.from_dict(timeline_data)

        w, h = tl.width, tl.height
        fps = tl.fps
        total_dur = tl.duration
        total_frames = int(total_dur * fps)

        if total_frames <= 0:
            raise ValueError("Timeline vazia")

        print(f"[Render] {w}x{h} @ {fps}fps, {total_dur:.1f}s, {total_frames} frames")

        # Abre todos os vídeos fonte
        sources = {}
        for track in tl.tracks:
            for clip in track.clips:
                if clip.source_path and clip.source_path not in sources:
                    cap = cv2.VideoCapture(clip.source_path)
                    if cap.isOpened():
                        sources[clip.source_path] = {
                            "cap": cap,
                            "fps": cap.get(cv2.CAP_PROP_FPS),
                            "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                            "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                        }

        # Renderiza frame a frame
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        temp_video = output_path + ".temp.mp4"
        writer = cv2.VideoWriter(temp_video, fourcc, fps, (w, h))

        for frame_idx in range(total_frames):
            t = frame_idx / fps
            canvas = np.zeros((h, w, 3), dtype=np.uint8)

            # Renderiza tracks de baixo para cima (V1 -> V2 -> V3)
            video_tracks = [tk for tk in tl.tracks if tk.track_type in ("video", "overlay")]
            video_tracks.reverse()  # V1 primeiro, V3 por cima

            for track in video_tracks:
                if track.muted or not track.visible:
                    continue
                clip = track.get_clip_at(t)
                if not clip or not clip.source_path:
                    continue

                src = sources.get(clip.source_path)
                if not src:
                    # Pode ser imagem
                    if Path(clip.source_path).suffix.lower() in (".png", ".jpg", ".jpeg"):
                        img = cv2.imread(clip.source_path, cv2.IMREAD_UNCHANGED)
                        if img is not None:
                            self._composite(canvas, img, clip, t, w, h)
                    continue

                # Calcula frame do source
                local_t = t - clip.timeline_start + clip.source_start
                src_frame = int(local_t * src["fps"])
                src["cap"].set(cv2.CAP_PROP_POS_FRAMES, src_frame)
                ret, frame = src["cap"].read()
                if not ret:
                    continue

                self._composite(canvas, frame, clip, t, w, h)

            writer.write(canvas)

            if frame_idx % 100 == 0:
                pct = frame_idx / total_frames
                print(f"[Render] {pct*100:.0f}%")
                if self.progress_callback:
                    self.progress_callback(pct)

        writer.release()
        for s in sources.values():
            s["cap"].release()

        # Mux audio
        self._mux_audio(temp_video, tl, output_path)
        Path(temp_video).unlink(missing_ok=True)

        print(f"[Render] Completo: {output_path}")
        return output_path

    def _composite(self, canvas, frame, clip, t, canvas_w, canvas_h):
        """Compõe frame do clip sobre o canvas usando keyframes."""
        transform = clip.get_transform_at(t)
        scale = max(0.01, transform["scale"])
        opacity = max(0, min(1, transform["opacity"]))
        px = transform["position_x"]
        py = transform["position_y"]

        if opacity <= 0:
            return

        fh, fw = frame.shape[:2]

        # Calcula crop para caber no canvas respeitando posição
        # (reframe baseado no anchor point)
        target_aspect = canvas_w / canvas_h
        src_aspect = fw / fh

        if src_aspect > target_aspect:
            # Source mais largo: crop horizontal
            crop_h = fh
            crop_w = int(fh * target_aspect)
        else:
            crop_w = fw
            crop_h = int(fw / target_aspect)

        # Aplica scale (zoom)
        crop_w = int(crop_w / scale)
        crop_h = int(crop_h / scale)
        crop_w = max(10, min(fw, crop_w))
        crop_h = max(10, min(fh, crop_h))

        # Posição do crop centrada no anchor
        cx = int(px * fw)
        cy = int(py * fh)
        x0 = max(0, min(fw - crop_w, cx - crop_w // 2))
        y0 = max(0, min(fh - crop_h, cy - crop_h // 2))

        cropped = frame[y0:y0+crop_h, x0:x0+crop_w]
        if cropped.size == 0:
            return

        resized = cv2.resize(cropped, (canvas_w, canvas_h))

        # Aplica opacidade
        if opacity < 1.0:
            if frame.shape[2] == 4:  # BGRA
                alpha = frame[:, :, 3:4] / 255.0 * opacity
                resized_rgb = resized[:, :, :3]
                canvas[:] = (canvas * (1 - alpha) + resized_rgb * alpha).astype(np.uint8)
                return
            else:
                cv2.addWeighted(resized, opacity, canvas, 1 - opacity, 0, canvas)
                return

        canvas[:] = resized

    def _mux_audio(self, video_path: str, tl, output_path: str):
        """Adiciona áudio do primeiro clip de áudio."""
        audio_tracks = [tk for tk in tl.tracks if tk.track_type in ("audio", "music")]
        audio_src = None
        for at in audio_tracks:
            if at.clips and not at.muted:
                audio_src = at.clips[0].source_path
                break

        if audio_src and Path(audio_src).exists():
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path, "-i", audio_src,
                "-c:v", "libx264", "-crf", str(EXPORT_CRF),
                "-preset", EXPORT_PRESET,
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                output_path,
            ]
            subprocess.run(cmd, capture_output=True, check=False)
        else:
            # Encode sem áudio
            cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-c:v", "libx264", "-crf", str(EXPORT_CRF),
                "-preset", EXPORT_PRESET,
                "-an", output_path,
            ]
            subprocess.run(cmd, capture_output=True, check=False)
