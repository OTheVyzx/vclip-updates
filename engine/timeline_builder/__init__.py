"""Vclip - Timeline Builder: modelo de dados profissional.

Estrutura interna semelhante a Premiere/DaVinci:
  Project → Timeline → Track → Clip → Effect → Keyframe

Serialização em JSON para persistência e comunicação com UI.
"""

import json
import copy
import time
from pathlib import Path
from typing import List, Dict, Optional, Any


# ─── Keyframe ─────────────────────────────────────────
class Keyframe:
    """Ponto de controle para animação de propriedade."""

    EASINGS = ["linear", "ease_in", "ease_out", "ease_in_out", "bezier", "hold"]

    def __init__(self, time: float, value: float, easing: str = "ease_in_out"):
        self.time = time
        self.value = value
        self.easing = easing if easing in self.EASINGS else "linear"

    def to_dict(self):
        return {"time": self.time, "value": self.value, "easing": self.easing}

    @staticmethod
    def from_dict(d: dict):
        return Keyframe(d["time"], d["value"], d.get("easing", "linear"))


# ─── Envelope (lista de keyframes para uma propriedade) ─
class Envelope:
    """Curva de animação: lista ordenada de keyframes."""

    def __init__(self, property_name: str, default: float = 0.0):
        self.property_name = property_name
        self.default = default
        self.keyframes: List[Keyframe] = []

    def add(self, time: float, value: float, easing: str = "ease_in_out"):
        kf = Keyframe(time, value, easing)
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.time)
        return kf

    def remove_at(self, index: int):
        if 0 <= index < len(self.keyframes):
            self.keyframes.pop(index)

    def get_value_at(self, t: float) -> float:
        """Interpola valor no tempo t."""
        if not self.keyframes:
            return self.default
        if t <= self.keyframes[0].time:
            return self.keyframes[0].value
        if t >= self.keyframes[-1].time:
            return self.keyframes[-1].value

        # Encontra segmento
        for i in range(len(self.keyframes) - 1):
            k0 = self.keyframes[i]
            k1 = self.keyframes[i + 1]
            if k0.time <= t <= k1.time:
                progress = (t - k0.time) / max(k1.time - k0.time, 0.001)
                eased = self._apply_easing(progress, k1.easing)
                return k0.value + (k1.value - k0.value) * eased
        return self.default

    def _apply_easing(self, p: float, easing: str) -> float:
        if easing == "linear":
            return p
        elif easing == "ease_in":
            return p * p * p
        elif easing == "ease_out":
            return 1 - (1 - p) ** 3
        elif easing == "ease_in_out":
            return 4*p*p*p if p < 0.5 else 1 - ((-2*p + 2)**3)/2
        elif easing == "hold":
            return 0.0
        elif easing == "bezier":
            # Cubic bezier approximation
            return 3*p*p - 2*p*p*p
        return p

    def to_dict(self):
        return {
            "property": self.property_name,
            "default": self.default,
            "keyframes": [k.to_dict() for k in self.keyframes],
        }

    @staticmethod
    def from_dict(d: dict):
        env = Envelope(d["property"], d.get("default", 0))
        for kd in d.get("keyframes", []):
            env.keyframes.append(Keyframe.from_dict(kd))
        return env


# ─── Effect ───────────────────────────────────────────
class Effect:
    """Efeito aplicado a um clip com envelopes parametrizados."""

    def __init__(self, effect_type: str, **params):
        self.effect_type = effect_type  # "zoom", "position", "opacity", "insert", "subtitle"
        self.enabled = True
        self.params = params  # static params
        self.envelopes: Dict[str, Envelope] = {}

    def add_envelope(self, prop: str, default: float = 0.0) -> Envelope:
        env = Envelope(prop, default)
        self.envelopes[prop] = env
        return env

    def get_param_at(self, prop: str, t: float) -> float:
        if prop in self.envelopes:
            return self.envelopes[prop].get_value_at(t)
        return self.params.get(prop, 0.0)

    def to_dict(self):
        return {
            "effect_type": self.effect_type,
            "enabled": self.enabled,
            "params": self.params,
            "envelopes": {k: v.to_dict() for k, v in self.envelopes.items()},
        }

    @staticmethod
    def from_dict(d: dict):
        eff = Effect(d["effect_type"], **d.get("params", {}))
        eff.enabled = d.get("enabled", True)
        for key, envd in d.get("envelopes", {}).items():
            eff.envelopes[key] = Envelope.from_dict(envd)
        return eff


# ─── Clip ─────────────────────────────────────────────
class TimelineClip:
    """Clip na timeline com posição, efeitos e keyframes."""

    _counter = 0

    def __init__(
        self,
        source_path: str,
        timeline_start: float,
        timeline_end: float,
        source_start: float = 0.0,
        source_end: float = None,
        label: str = "",
    ):
        TimelineClip._counter += 1
        self.id = f"clip_{TimelineClip._counter}"
        self.source_path = source_path
        self.timeline_start = timeline_start
        self.timeline_end = timeline_end
        self.source_start = source_start
        self.source_end = source_end or (timeline_end - timeline_start)
        self.label = label
        self.effects: List[Effect] = []
        self.metadata: Dict[str, Any] = {}

        # Transform envelopes (editable via UI)
        self.position_x = Envelope("position_x", 0.5)   # 0-1 normalized
        self.position_y = Envelope("position_y", 0.5)
        self.scale = Envelope("scale", 1.0)
        self.opacity = Envelope("opacity", 1.0)
        self.rotation = Envelope("rotation", 0.0)

    @property
    def duration(self):
        return self.timeline_end - self.timeline_start

    def add_effect(self, effect: Effect):
        self.effects.append(effect)
        return effect

    def get_transform_at(self, t: float) -> dict:
        """Retorna transform completo no tempo t (relativo ao clip)."""
        local_t = t - self.timeline_start
        return {
            "position_x": self.position_x.get_value_at(local_t),
            "position_y": self.position_y.get_value_at(local_t),
            "scale": self.scale.get_value_at(local_t),
            "opacity": self.opacity.get_value_at(local_t),
            "rotation": self.rotation.get_value_at(local_t),
        }

    def to_dict(self):
        return {
            "id": self.id,
            "source_path": self.source_path,
            "timeline_start": self.timeline_start,
            "timeline_end": self.timeline_end,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "label": self.label,
            "effects": [e.to_dict() for e in self.effects],
            "metadata": self.metadata,
            "position_x": self.position_x.to_dict(),
            "position_y": self.position_y.to_dict(),
            "scale": self.scale.to_dict(),
            "opacity": self.opacity.to_dict(),
            "rotation": self.rotation.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict):
        clip = TimelineClip(
            d["source_path"], d["timeline_start"], d["timeline_end"],
            d.get("source_start", 0), d.get("source_end"),
            d.get("label", ""),
        )
        clip.id = d.get("id", clip.id)
        clip.metadata = d.get("metadata", {})
        for ed in d.get("effects", []):
            clip.effects.append(Effect.from_dict(ed))
        for prop in ["position_x", "position_y", "scale", "opacity", "rotation"]:
            if prop in d:
                setattr(clip, prop, Envelope.from_dict(d[prop]))
        return clip


# ─── Track ────────────────────────────────────────────
class Track:
    """Track contém clips do mesmo tipo."""

    TYPES = ["video", "audio", "subtitle", "overlay", "music"]

    def __init__(self, name: str, track_type: str = "video"):
        self.name = name
        self.track_type = track_type if track_type in self.TYPES else "video"
        self.clips: List[TimelineClip] = []
        self.muted = False
        self.solo = False
        self.locked = False
        self.volume = 1.0  # for audio tracks
        self.visible = True

    def add_clip(self, clip: TimelineClip) -> TimelineClip:
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.timeline_start)
        return clip

    def remove_clip(self, clip_id: str):
        self.clips = [c for c in self.clips if c.id != clip_id]

    def get_clip_at(self, t: float) -> Optional[TimelineClip]:
        for c in self.clips:
            if c.timeline_start <= t <= c.timeline_end:
                return c
        return None

    @property
    def duration(self):
        if not self.clips:
            return 0
        return max(c.timeline_end for c in self.clips)

    def to_dict(self):
        return {
            "name": self.name,
            "track_type": self.track_type,
            "muted": self.muted,
            "solo": self.solo,
            "locked": self.locked,
            "volume": self.volume,
            "visible": self.visible,
            "clips": [c.to_dict() for c in self.clips],
        }

    @staticmethod
    def from_dict(d: dict):
        track = Track(d["name"], d.get("track_type", "video"))
        track.muted = d.get("muted", False)
        track.solo = d.get("solo", False)
        track.locked = d.get("locked", False)
        track.volume = d.get("volume", 1.0)
        track.visible = d.get("visible", True)
        for cd in d.get("clips", []):
            track.clips.append(TimelineClip.from_dict(cd))
        return track


# ─── Timeline ────────────────────────────────────────
class Timeline:
    """Timeline completa com tracks, configurações e metadados."""

    def __init__(self, name: str = "Untitled", fps: float = 30.0):
        self.name = name
        self.fps = fps
        self.width = 1080
        self.height = 1920
        self.aspect_ratio = "9:16"
        self.tracks: List[Track] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = time.time()
        self.modified_at = time.time()

    def set_format(self, aspect: str):
        """Define formato de saída: 9:16, 16:9, 1:1, 4:5, ou WxH."""
        formats = {
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "1:1": (1080, 1080),
            "4:5": (1080, 1350),
        }
        if aspect in formats:
            self.width, self.height = formats[aspect]
            self.aspect_ratio = aspect
        elif "x" in aspect.lower():
            parts = aspect.lower().split("x")
            self.width, self.height = int(parts[0]), int(parts[1])
            self.aspect_ratio = f"{self.width}:{self.height}"

    def add_track(self, name: str, track_type: str = "video") -> Track:
        track = Track(name, track_type)
        self.tracks.append(track)
        return track

    def get_track(self, name: str) -> Optional[Track]:
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    def remove_track(self, name: str):
        self.tracks = [t for t in self.tracks if t.name != name]

    @property
    def duration(self):
        if not self.tracks:
            return 0
        return max((t.duration for t in self.tracks), default=0)

    def find_clip(self, clip_id: str) -> Optional[TimelineClip]:
        for track in self.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return clip
        return None

    def move_clip(self, clip_id: str, new_start: float):
        clip = self.find_clip(clip_id)
        if clip:
            dur = clip.duration
            clip.timeline_start = max(0, new_start)
            clip.timeline_end = clip.timeline_start + dur
            self.modified_at = time.time()

    def trim_clip(self, clip_id: str, new_start: float = None, new_end: float = None):
        clip = self.find_clip(clip_id)
        if clip:
            if new_start is not None:
                clip.timeline_start = max(0, new_start)
            if new_end is not None:
                clip.timeline_end = max(clip.timeline_start + 0.1, new_end)
            self.modified_at = time.time()

    def to_dict(self):
        return {
            "name": self.name,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "tracks": [t.to_dict() for t in self.tracks],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "duration": self.duration,
        }

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                      encoding="utf-8")

    @staticmethod
    def from_dict(d: dict):
        tl = Timeline(d.get("name", "Untitled"), d.get("fps", 30))
        tl.width = d.get("width", 1080)
        tl.height = d.get("height", 1920)
        tl.aspect_ratio = d.get("aspect_ratio", "9:16")
        tl.metadata = d.get("metadata", {})
        tl.created_at = d.get("created_at", time.time())
        tl.modified_at = d.get("modified_at", time.time())
        for td in d.get("tracks", []):
            tl.tracks.append(Track.from_dict(td))
        return tl

    @staticmethod
    def load(path: str):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Timeline.from_dict(data)


# ─── Builder helper ──────────────────────────────────
class TimelineBuilder:
    """Helper para construir timeline a partir do pipeline."""

    def __init__(self, aspect: str = "9:16", fps: float = 30.0):
        self.timeline = Timeline("Vclip Project", fps)
        self.timeline.set_format(aspect)

        # Cria tracks padrão DaVinci-style
        self.timeline.add_track("C1", "subtitle")
        self.timeline.add_track("V3", "overlay")
        self.timeline.add_track("V2", "video")
        self.timeline.add_track("V1", "video")
        self.timeline.add_track("A1", "audio")
        self.timeline.add_track("A2", "audio")
        self.timeline.add_track("A3", "music")

    def add_video_clip(self, path: str, start: float, end: float,
                       label: str = "", face_data: dict = None) -> TimelineClip:
        track = self.timeline.get_track("V1")
        clip = TimelineClip(path, start, end, label=label)

        # Se tiver face data, cria keyframes de posição
        if face_data:
            fps = face_data.get("fps", 30)
            cx_list = face_data.get("face_centers_x", [])
            cy_list = face_data.get("face_centers_y", [])
            # Sample keyframes a cada 0.5s
            step = max(1, int(fps * 0.5))
            for i in range(0, len(cx_list), step):
                t = i / fps
                if t > (end - start):
                    break
                clip.position_x.add(t, cx_list[i], "ease_in_out")
                clip.position_y.add(t, cy_list[i], "ease_in_out")

        track.add_clip(clip)
        return clip

    def add_audio_clip(self, path: str, start: float, end: float,
                       track_name: str = "A1", volume: float = 1.0):
        track = self.timeline.get_track(track_name)
        clip = TimelineClip(path, start, end, label=f"Audio")
        clip.metadata["volume"] = volume
        track.add_clip(clip)
        return clip

    def add_overlay(self, path: str, start: float, end: float,
                    opacity: float = 1.0):
        track = self.timeline.get_track("V3")
        clip = TimelineClip(path, start, end, label=Path(path).name)
        clip.opacity = Envelope("opacity", opacity)
        track.add_clip(clip)
        return clip

    def add_subtitle(self, segments: list, start_offset: float = 0.0):
        track = self.timeline.get_track("C1")
        for seg in segments:
            s = seg["start"] + start_offset
            e = seg["end"] + start_offset
            clip = TimelineClip("", s, e, label=seg.get("text", ""))
            clip.metadata["text"] = seg.get("text", "")
            clip.metadata["words"] = seg.get("words", [])
            track.add_clip(clip)

    def add_insert(self, path: str, start: float, duration: float = 1.0,
                   opacity: float = 1.0, position: str = "cover"):
        track = self.timeline.get_track("V3")
        clip = TimelineClip(path, start, start + duration, label="Insert")
        clip.metadata["insert_position"] = position
        clip.opacity = Envelope("opacity", opacity)
        # Fade in/out
        clip.opacity.add(0, 0, "ease_in")
        clip.opacity.add(0.2, opacity, "ease_in_out")
        clip.opacity.add(duration - 0.2, opacity, "ease_out")
        clip.opacity.add(duration, 0, "ease_out")
        track.add_clip(clip)
        return clip

    def add_music(self, path: str, volume_db: float = -28):
        import math
        vol = math.pow(10, volume_db / 20)
        dur = self.timeline.duration
        track = self.timeline.get_track("A3")
        clip = TimelineClip(path, 0, dur, label=Path(path).name)
        clip.metadata["volume_db"] = volume_db
        clip.metadata["volume_linear"] = vol
        track.add_clip(clip)
        return clip

    def build(self) -> Timeline:
        self.timeline.modified_at = time.time()
        return self.timeline
