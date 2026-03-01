"""Vclip - Timeline Data Models.

Professional timeline system with keyframes, envelopes, and easing.
Serializable to JSON for UI sync and project save/load.

Inspired by Premiere/DaVinci internal structure:
  Project → Timeline → Track[] → Clip[] → Effect[] → Keyframe[]
"""

import json
import time
import uuid
import math
from pathlib import Path
from typing import List, Dict, Optional, Any


# ─── Easing Functions ────────────────────────────────

def ease_linear(t: float) -> float:
    return t

def ease_in_quad(t: float) -> float:
    return t * t

def ease_out_quad(t: float) -> float:
    return t * (2 - t)

def ease_in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

def ease_in_cubic(t: float) -> float:
    return t ** 3

def ease_out_cubic(t: float) -> float:
    return (t - 1) ** 3 + 1

def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t ** 3
    return 1 - ((-2 * t + 2) ** 3) / 2

def ease_bezier(t: float, p1x=0.42, p1y=0.0, p2x=0.58, p2y=1.0) -> float:
    """Cubic bezier approximation."""
    cx = 3 * p1x
    bx = 3 * (p2x - p1x) - cx
    ax = 1 - cx - bx
    cy = 3 * p1y
    by = 3 * (p2y - p1y) - cy
    ay = 1 - cy - by
    return ((ay * t + by) * t + cy) * t

EASING_MAP = {
    "linear": ease_linear,
    "ease_in": ease_in_quad,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "bezier": ease_bezier,
}


# ─── Keyframe ────────────────────────────────────────

class Keyframe:
    """Single keyframe with time, value, and easing."""

    def __init__(self, time: float, value: float, easing: str = "ease_in_out_cubic"):
        self.id = str(uuid.uuid4())[:8]
        self.time = time
        self.value = value
        self.easing = easing

    def to_dict(self) -> dict:
        return {"id": self.id, "time": self.time, "value": self.value, "easing": self.easing}

    @classmethod
    def from_dict(cls, d: dict) -> "Keyframe":
        kf = cls(d["time"], d["value"], d.get("easing", "ease_in_out_cubic"))
        kf.id = d.get("id", kf.id)
        return kf


# ─── Envelope (Keyframe Track) ───────────────────────

class Envelope:
    """Collection of keyframes for a single parameter (e.g., scale, pos_x)."""

    def __init__(self, param_name: str, default_value: float = 0.0):
        self.param_name = param_name
        self.default_value = default_value
        self.keyframes: List[Keyframe] = []

    def add_keyframe(self, time: float, value: float, easing: str = "ease_in_out_cubic") -> Keyframe:
        kf = Keyframe(time, value, easing)
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.time)
        return kf

    def remove_keyframe(self, kf_id: str):
        self.keyframes = [k for k in self.keyframes if k.id != kf_id]

    def update_keyframe(self, kf_id: str, time: float = None, value: float = None, easing: str = None):
        for kf in self.keyframes:
            if kf.id == kf_id:
                if time is not None: kf.time = time
                if value is not None: kf.value = value
                if easing is not None: kf.easing = easing
                self.keyframes.sort(key=lambda k: k.time)
                return kf
        return None

    def get_value_at(self, time: float) -> float:
        """Interpolate value at given time using easing between keyframes."""
        if not self.keyframes:
            return self.default_value

        # Before first keyframe
        if time <= self.keyframes[0].time:
            return self.keyframes[0].value

        # After last keyframe
        if time >= self.keyframes[-1].time:
            return self.keyframes[-1].value

        # Find surrounding keyframes
        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i + 1]
            if k1.time <= time <= k2.time:
                duration = k2.time - k1.time
                if duration <= 0:
                    return k2.value
                t = (time - k1.time) / duration
                ease_fn = EASING_MAP.get(k2.easing, ease_linear)
                eased_t = ease_fn(t)
                return k1.value + (k2.value - k1.value) * eased_t

        return self.default_value

    def to_dict(self) -> dict:
        return {
            "param_name": self.param_name,
            "default_value": self.default_value,
            "keyframes": [kf.to_dict() for kf in self.keyframes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Envelope":
        env = cls(d["param_name"], d.get("default_value", 0.0))
        for kf_d in d.get("keyframes", []):
            kf = Keyframe.from_dict(kf_d)
            env.keyframes.append(kf)
        env.keyframes.sort(key=lambda k: k.time)
        return env


# ─── Effect ──────────────────────────────────────────

class Effect:
    """Effect applied to a clip with parameterized envelopes."""

    def __init__(self, name: str, effect_type: str = "transform"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.effect_type = effect_type  # transform, filter, audio, subtitle
        self.enabled = True
        self.envelopes: Dict[str, Envelope] = {}

    def add_envelope(self, param_name: str, default_value: float = 0.0) -> Envelope:
        env = Envelope(param_name, default_value)
        self.envelopes[param_name] = env
        return env

    def get_param_at(self, param_name: str, time: float) -> float:
        env = self.envelopes.get(param_name)
        if env:
            return env.get_value_at(time)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "effect_type": self.effect_type,
            "enabled": self.enabled,
            "envelopes": {k: v.to_dict() for k, v in self.envelopes.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Effect":
        fx = cls(d["name"], d.get("effect_type", "transform"))
        fx.id = d.get("id", fx.id)
        fx.enabled = d.get("enabled", True)
        for k, v in d.get("envelopes", {}).items():
            fx.envelopes[k] = Envelope.from_dict(v)
        return fx


# ─── Clip ────────────────────────────────────────────

class TimelineClip:
    """Single clip on a track."""

    def __init__(
        self,
        source_path: str = "",
        start_time: float = 0.0,
        end_time: float = 0.0,
        source_in: float = 0.0,
        source_out: float = 0.0,
        label: str = "",
    ):
        self.id = str(uuid.uuid4())[:8]
        self.source_path = source_path
        self.start_time = start_time   # position on timeline
        self.end_time = end_time
        self.source_in = source_in     # trim point in source
        self.source_out = source_out
        self.label = label
        self.enabled = True
        self.locked = False
        self.effects: List[Effect] = []
        self.metadata: Dict[str, Any] = {}

        # Quick-access transform (also accessible via effects)
        self.position_x = 0.0
        self.position_y = 0.0
        self.scale = 1.0
        self.rotation = 0.0
        self.opacity = 1.0
        self.volume = 1.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def add_transform_effect(self) -> Effect:
        """Add default transform effect with position/scale/opacity envelopes."""
        fx = Effect("Transform", "transform")
        fx.add_envelope("position_x", self.position_x)
        fx.add_envelope("position_y", self.position_y)
        fx.add_envelope("scale", self.scale)
        fx.add_envelope("rotation", self.rotation)
        fx.add_envelope("opacity", self.opacity)
        self.effects.append(fx)
        return fx

    def add_zoom_effect(self, keyframes: list = None) -> Effect:
        """Add zoom effect with keyframes [(time, scale), ...]."""
        fx = Effect("Zoom", "transform")
        env = fx.add_envelope("zoom", 1.0)
        if keyframes:
            for t, v in keyframes:
                env.add_keyframe(t, v)
        self.effects.append(fx)
        return fx

    def get_transform_at(self, time: float) -> dict:
        """Get interpolated transform values at a specific time."""
        result = {
            "position_x": self.position_x,
            "position_y": self.position_y,
            "scale": self.scale,
            "rotation": self.rotation,
            "opacity": self.opacity,
        }
        for fx in self.effects:
            if fx.effect_type == "transform" and fx.enabled:
                for param in result:
                    if param in fx.envelopes:
                        result[param] = fx.get_param_at(param, time)
        return result

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "start_time": round(self.start_time, 3),
            "end_time": round(self.end_time, 3),
            "source_in": round(self.source_in, 3),
            "source_out": round(self.source_out, 3),
            "label": self.label,
            "enabled": self.enabled,
            "locked": self.locked,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "scale": self.scale,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "volume": self.volume,
            "effects": [fx.to_dict() for fx in self.effects],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineClip":
        clip = cls(
            source_path=d.get("source_path", ""),
            start_time=d.get("start_time", 0),
            end_time=d.get("end_time", 0),
            source_in=d.get("source_in", 0),
            source_out=d.get("source_out", 0),
            label=d.get("label", ""),
        )
        clip.id = d.get("id", clip.id)
        clip.enabled = d.get("enabled", True)
        clip.locked = d.get("locked", False)
        clip.position_x = d.get("position_x", 0)
        clip.position_y = d.get("position_y", 0)
        clip.scale = d.get("scale", 1.0)
        clip.rotation = d.get("rotation", 0)
        clip.opacity = d.get("opacity", 1.0)
        clip.volume = d.get("volume", 1.0)
        clip.metadata = d.get("metadata", {})
        for fx_d in d.get("effects", []):
            clip.effects.append(Effect.from_dict(fx_d))
        return clip


# ─── Track ───────────────────────────────────────────

class Track:
    """Single track in the timeline."""

    TYPES = ("video", "audio", "subtitle", "overlay")

    def __init__(self, name: str, track_type: str = "video", index: int = 0):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.track_type = track_type
        self.index = index
        self.clips: List[TimelineClip] = []
        self.muted = False
        self.solo = False
        self.locked = False
        self.visible = True
        self.volume = 1.0  # for audio tracks
        self.height = 32   # UI track height in px

    def add_clip(self, clip: TimelineClip) -> TimelineClip:
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start_time)
        return clip

    def remove_clip(self, clip_id: str):
        self.clips = [c for c in self.clips if c.id != clip_id]

    def get_clip_at(self, time: float) -> Optional[TimelineClip]:
        for clip in self.clips:
            if clip.start_time <= time <= clip.end_time:
                return clip
        return None

    def move_clip(self, clip_id: str, new_start: float):
        for clip in self.clips:
            if clip.id == clip_id and not clip.locked:
                dur = clip.duration
                clip.start_time = max(0, new_start)
                clip.end_time = clip.start_time + dur
        self.clips.sort(key=lambda c: c.start_time)

    def trim_clip(self, clip_id: str, new_start: float = None, new_end: float = None):
        for clip in self.clips:
            if clip.id == clip_id and not clip.locked:
                if new_start is not None:
                    clip.start_time = new_start
                if new_end is not None:
                    clip.end_time = new_end

    def split_clip(self, clip_id: str, split_time: float) -> Optional[TimelineClip]:
        """Split a clip at split_time, return the new right clip."""
        for i, clip in enumerate(self.clips):
            if clip.id == clip_id and clip.start_time < split_time < clip.end_time:
                # Create right portion
                right = TimelineClip(
                    source_path=clip.source_path,
                    start_time=split_time,
                    end_time=clip.end_time,
                    source_in=clip.source_in + (split_time - clip.start_time),
                    source_out=clip.source_out,
                    label=clip.label + " (R)",
                )
                right.volume = clip.volume
                right.scale = clip.scale
                right.position_x = clip.position_x
                right.position_y = clip.position_y
                # Trim original to left
                clip.end_time = split_time
                clip.source_out = clip.source_in + clip.duration
                clip.label = clip.label.replace(" (R)", "") + " (L)" if "(L)" not in clip.label else clip.label
                self.clips.insert(i + 1, right)
                return right
        return None

    @property
    def total_duration(self) -> float:
        if not self.clips:
            return 0
        return max(c.end_time for c in self.clips)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "track_type": self.track_type,
            "index": self.index,
            "muted": self.muted,
            "solo": self.solo,
            "locked": self.locked,
            "visible": self.visible,
            "volume": self.volume,
            "height": self.height,
            "clips": [c.to_dict() for c in self.clips],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        track = cls(d["name"], d.get("track_type", "video"), d.get("index", 0))
        track.id = d.get("id", track.id)
        track.muted = d.get("muted", False)
        track.solo = d.get("solo", False)
        track.locked = d.get("locked", False)
        track.visible = d.get("visible", True)
        track.volume = d.get("volume", 1.0)
        track.height = d.get("height", 32)
        for c_d in d.get("clips", []):
            track.clips.append(TimelineClip.from_dict(c_d))
        return track


# ─── Timeline ────────────────────────────────────────

class Timeline:
    """Complete project timeline with tracks, clips, and effects."""

    def __init__(self, name: str = "Untitled"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.created_at = time.time()
        self.modified_at = time.time()
        self.fps = 30
        self.sample_rate = 48000
        self.tracks: List[Track] = []

        # Output format
        self.output_width = 1080
        self.output_height = 1920
        self.aspect_ratio = "9:16"

        # Project settings
        self.settings: Dict[str, Any] = {}

    @property
    def duration(self) -> float:
        if not self.tracks:
            return 0
        return max((t.total_duration for t in self.tracks), default=0)

    def create_default_tracks(self):
        """Create default track layout like DaVinci."""
        defaults = [
            ("C1 - Legenda", "subtitle", 0),
            ("V3 - Overlay", "overlay", 1),
            ("V2 - Efeitos", "video", 2),
            ("V1 - Vídeo", "video", 3),
            ("A1 - Áudio", "audio", 4),
            ("A2 - Áudio 2", "audio", 5),
            ("A3 - Música", "audio", 6),
        ]
        for name, ttype, idx in defaults:
            self.tracks.append(Track(name, ttype, idx))

    def add_track(self, name: str, track_type: str = "video") -> Track:
        idx = len(self.tracks)
        track = Track(name, track_type, idx)
        self.tracks.append(track)
        return track

    def get_track(self, name: str) -> Optional[Track]:
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    def get_track_by_index(self, index: int) -> Optional[Track]:
        for t in self.tracks:
            if t.index == index:
                return t
        return None

    def find_clip(self, clip_id: str) -> Optional[tuple]:
        """Find clip by id. Returns (track, clip) or None."""
        for track in self.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return track, clip
        return None

    def set_output_format(self, width: int, height: int, aspect: str = None):
        self.output_width = width
        self.output_height = height
        if aspect:
            self.aspect_ratio = aspect
        else:
            from math import gcd
            g = gcd(width, height)
            self.aspect_ratio = f"{width // g}:{height // g}"

    def to_dict(self) -> dict:
        self.modified_at = time.time()
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "fps": self.fps,
            "sample_rate": self.sample_rate,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "aspect_ratio": self.aspect_ratio,
            "duration": round(self.duration, 3),
            "settings": self.settings,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "Timeline":
        tl = cls(d.get("name", "Untitled"))
        tl.id = d.get("id", tl.id)
        tl.created_at = d.get("created_at", tl.created_at)
        tl.modified_at = d.get("modified_at", tl.modified_at)
        tl.fps = d.get("fps", 30)
        tl.sample_rate = d.get("sample_rate", 48000)
        tl.output_width = d.get("output_width", 1080)
        tl.output_height = d.get("output_height", 1920)
        tl.aspect_ratio = d.get("aspect_ratio", "9:16")
        tl.settings = d.get("settings", {})
        for t_d in d.get("tracks", []):
            tl.tracks.append(Track.from_dict(t_d))
        return tl

    @classmethod
    def load(cls, path: str) -> "Timeline":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ─── Format Presets ──────────────────────────────────

FORMAT_PRESETS = {
    "16:9": {"width": 1920, "height": 1080, "aspect": "16:9"},
    "9:16": {"width": 1080, "height": 1920, "aspect": "9:16"},
    "1:1":  {"width": 1080, "height": 1080, "aspect": "1:1"},
    "4:5":  {"width": 1080, "height": 1350, "aspect": "4:5"},
    "4:3":  {"width": 1440, "height": 1080, "aspect": "4:3"},
}
