"""Vclip - Configuração central do motor de edição."""

import json
from pathlib import Path


# ─── Vídeo ────────────────────────────────────────────────
FPS = 30
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_ASPECT = "9:16"

# Multi-formato
OUTPUT_FORMATS = {
    "16:9": {"width": 1920, "height": 1080},
    "9:16": {"width": 1080, "height": 1920},
    "1:1":  {"width": 1080, "height": 1080},
    "4:5":  {"width": 1080, "height": 1350},
    "4:3":  {"width": 1440, "height": 1080},
}

# ─── Transcrição ──────────────────────────────────────────
WHISPER_MODEL_SIZE = "medium"
WHISPER_LANGUAGE = "pt"

# ─── Remoção de Silêncio ─────────────────────────────────
SILENCE_MIN_LEN_MS = 300          # ms mínimo para considerar silêncio
SILENCE_PADDING_START_MS = 80     # ms mantidos antes da fala
SILENCE_PADDING_END_MS = 120      # ms mantidos depois da fala
SILENCE_EXTENSION_MAX_MS = 400    # extensão máxima para capturar final natural
SILENCE_THRESHOLD_OFFSET_DB = 12  # dB abaixo da média = threshold

# ─── Clip Detector ────────────────────────────────────────
CLIP_MIN_DURATION = 6
CLIP_MAX_BLOCK_DURATION = 15
CLIP_PAUSE_THRESHOLD = 0.4
CLIP_POWER_WORDS = [
    "guerra", "medo", "verdade", "instinto", "matar",
    "força", "pátria", "preparado", "dinheiro", "poder",
    "morte", "vida", "problema", "solução", "incrível",
]

# ─── Zoom Engine ──────────────────────────────────────────
ZOOM_BASE_SCALE = 1.0
ZOOM_IN_SCALE = 1.12
ZOOM_TRANSITION_FRAMES = 12
ZOOM_MICRO_FRAMES = 8
ZOOM_MICRO_INTENSITY = 0.03
ZOOM_ENERGY_THRESHOLD = 1.4
ZOOM_COOLDOWN_FRAMES = 15

# ─── Face Tracking / Reframe ─────────────────────────────
FACE_DETECTION_CONFIDENCE = 0.5
FACE_SMOOTHING_WINDOW = 15        # frames para suavização

# ─── Legendas ─────────────────────────────────────────────
SUBTITLE_FONT = "Arial"
SUBTITLE_FONT_SIZE = 48
SUBTITLE_COLOR = "white"
SUBTITLE_OUTLINE_COLOR = "black"
SUBTITLE_OUTLINE_WIDTH = 3
SUBTITLE_POSITION = "bottom"      # bottom | center
SUBTITLE_MAX_CHARS_PER_LINE = 35
SUBTITLE_MARGIN_BOTTOM = 180

# ─── Exportação ───────────────────────────────────────────
EXPORT_CODEC = "libx264"
EXPORT_AUDIO_CODEC = "aac"
EXPORT_PRESET = "medium"
EXPORT_CRF = 18
EXPORT_AUDIO_BITRATE = "192k"


# ─── Presets de Cliente ───────────────────────────────────
DEFAULT_CLIENT_PRESET = {
    "name": "Default",
    "subtitle_font": SUBTITLE_FONT,
    "subtitle_font_size": SUBTITLE_FONT_SIZE,
    "subtitle_color": SUBTITLE_COLOR,
    "subtitle_outline_color": SUBTITLE_OUTLINE_COLOR,
    "zoom_intensity": ZOOM_IN_SCALE,
    "silence_aggressiveness": SILENCE_THRESHOLD_OFFSET_DB,
    "music_volume_db": -28,
    "reframe_mode": "center_dynamic",
}

CLIENT_PRESETS = {
    "padrinho_podcast": {
        "name": "O Padrinho Podcast",
        "subtitle_font": "Arial",
        "subtitle_font_size": 52,
        "subtitle_color": "#ffffff",
        "subtitle_outline_color": "#000000",
        "zoom_intensity": 1.12,
        "silence_aggressiveness": 12,
        "music_volume_db": -28,
        "reframe_mode": "center_dynamic",
    },
    "sucessora": {
        "name": "A Sucessora",
        "subtitle_font": "Arial",
        "subtitle_font_size": 48,
        "subtitle_color": "#ffffff",
        "subtitle_outline_color": "#000000",
        "zoom_intensity": 1.10,
        "silence_aggressiveness": 14,
        "music_volume_db": -30,
        "reframe_mode": "center_dynamic",
    },
    "djalma": {
        "name": "Djalma",
        "subtitle_font": "Arial",
        "subtitle_font_size": 50,
        "subtitle_color": "#ffff00",
        "subtitle_outline_color": "#000000",
        "zoom_intensity": 1.15,
        "silence_aggressiveness": 10,
        "music_volume_db": -26,
        "reframe_mode": "center_dynamic",
    },
}


def load_preset(client_key: str) -> dict:
    """Carrega preset de um cliente. Retorna default se não existir."""
    return CLIENT_PRESETS.get(client_key, DEFAULT_CLIENT_PRESET)


def save_preset(client_key: str, preset: dict, path: str = "config/presets.json"):
    """Salva presets em arquivo JSON."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing[client_key] = preset

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
