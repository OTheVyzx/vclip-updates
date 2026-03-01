"""Vclip - Timeline Builder.

Builds a professional Timeline from pipeline output.
Converts raw clips + face data + transcription into structured timeline
with tracks, clips, keyframes for position/zoom/opacity.
"""

from pathlib import Path
from engine.timeline_builder.models import (
    Timeline, Track, TimelineClip, Effect, Envelope,
    FORMAT_PRESETS,
)


class TimelineBuilder:
    """Builds timeline from pipeline results."""

    def build(
        self,
        clips_info: list,
        clip_paths: list,
        transcription: dict = None,
        face_data_list: list = None,
        overlay_path: str = None,
        music_path: str = None,
        music_volume: float = -28,
        format_preset: str = "9:16",
        client_name: str = "Default",
    ) -> Timeline:
        tl = Timeline(name=f"Vclip - {client_name}")

        # Set format
        fmt = FORMAT_PRESETS.get(format_preset, FORMAT_PRESETS["9:16"])
        tl.set_output_format(fmt["width"], fmt["height"], fmt["aspect"])

        # Create default tracks
        tl.create_default_tracks()

        v1 = tl.get_track("V1 - Vídeo")
        a1 = tl.get_track("A1 - Áudio")
        c1 = tl.get_track("C1 - Legenda")
        v3 = tl.get_track("V3 - Overlay")
        a3 = tl.get_track("A3 - Música")

        timeline_pos = 0.0

        for i, path in enumerate(clip_paths):
            info = clips_info[i] if i < len(clips_info) else {}
            dur = info.get("duration", 15.0)

            # Video clip on V1
            v_clip = TimelineClip(
                source_path=path,
                start_time=timeline_pos,
                end_time=timeline_pos + dur,
                source_in=0,
                source_out=dur,
                label=f"Corte{i+1:02d}.mp4 [V]",
            )

            # Add face tracking keyframes if available
            if face_data_list and i < len(face_data_list):
                fd = face_data_list[i]
                if fd:
                    transform = v_clip.add_transform_effect()
                    # Position X envelope from face tracking
                    env_x = transform.envelopes.get("position_x")
                    env_y = transform.envelopes.get("position_y")
                    env_scale = transform.envelopes.get("scale")

                    cx_list = fd.get("face_centers_x", [])
                    cy_list = fd.get("face_centers_y", [])
                    fps = fd.get("fps", 30)

                    # Sample every 15 frames for keyframes
                    step = max(1, len(cx_list) // 30)
                    for fi in range(0, len(cx_list), step):
                        t = fi / fps
                        if fi < len(cx_list) and env_x:
                            env_x.add_keyframe(t, cx_list[fi])
                        if fi < len(cy_list) and env_y:
                            env_y.add_keyframe(t, cy_list[fi])

            v1.add_clip(v_clip)

            # Audio clip on A1
            a_clip = TimelineClip(
                source_path=path,
                start_time=timeline_pos,
                end_time=timeline_pos + dur,
                label=f"Áudio {i+1:02d}",
            )
            a1.add_clip(a_clip)

            # Subtitle clip on C1 if transcription available
            if transcription and "segments" in transcription:
                segs = [s for s in transcription["segments"]
                        if info.get("start", 0) <= s.get("start", 0) <= info.get("end", 999999)]
                if segs:
                    sub_clip = TimelineClip(
                        start_time=timeline_pos,
                        end_time=timeline_pos + dur,
                        label="Legenda",
                    )
                    sub_clip.metadata["segments"] = segs[:50]
                    c1.add_clip(sub_clip)

            timeline_pos += dur

        # Overlay on V3 (full duration)
        if overlay_path and Path(overlay_path).is_file():
            ov_clip = TimelineClip(
                source_path=overlay_path,
                start_time=0,
                end_time=timeline_pos,
                label="layoutcorte.png",
            )
            v3.add_clip(ov_clip)

        # Music on A3
        if music_path and Path(music_path).is_file():
            import math
            vol_linear = math.pow(10, music_volume / 20)
            m_clip = TimelineClip(
                source_path=music_path,
                start_time=0,
                end_time=timeline_pos,
                label=Path(music_path).name,
            )
            m_clip.volume = vol_linear
            a3.add_clip(m_clip)

        return tl
