"""Vclip - API Server v2 com timeline editável.

Endpoints:
    GET  /api/status
    GET  /api/presets
    GET  /api/timeline           - Timeline atual (editável)
    GET  /api/version
    GET  /api/file/<path>        - Serve arquivos

    POST /api/process            - Pipeline completo
    POST /api/process-preview    - Pipeline até preview
    POST /api/export             - Exporta projeto
    POST /api/render             - Renderiza timeline editada
    POST /api/transcribe
    POST /api/learn-folder
    POST /api/save-preset

    POST /api/timeline/move-clip     - Move clip na timeline
    POST /api/timeline/trim-clip     - Trim clip
    POST /api/timeline/add-keyframe  - Adiciona keyframe
    POST /api/timeline/remove-clip   - Remove clip
    POST /api/timeline/set-format    - Muda formato (9:16, 16:9, etc)
    POST /api/timeline/undo
    POST /api/timeline/redo

    POST /api/update-check
    POST /api/update-apply
    POST /api/update-rollback
"""

import json
import threading
import time
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.pipeline import VclipPipeline
from engine.transcription import TranscriptionEngine
from engine.folder_learner import FolderLearner
from engine.update_manager import UpdateManager
from engine.state_manager import StateManager
from engine.config import CLIENT_PRESETS, load_preset, save_preset

state = {
    "status": "idle",
    "progress": 0,
    "current_step": "",
    "error": None,
    "version": "0.2.0",
}

timeline_data = None
state_mgr = StateManager()


def _thread(fn):
    threading.Thread(target=fn, daemon=True).start()


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/api/status":
            self._json(state)
        elif self.path == "/api/presets":
            self._json(CLIENT_PRESETS)
        elif self.path == "/api/timeline":
            self._get_timeline()
        elif self.path == "/api/version":
            self._json(UpdateManager().get_version_info())
        elif self.path.startswith("/api/file/"):
            self._serve_file(self.path[10:])
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        body = self._body()

        if self.path == "/api/process":
            self._process(body, False)
        elif self.path == "/api/process-preview":
            self._process(body, True)
        elif self.path == "/api/export":
            self._export(body)
        elif self.path == "/api/render":
            self._render(body)
        elif self.path == "/api/transcribe":
            self._transcribe(body)
        elif self.path == "/api/learn-folder":
            self._learn(body)
        elif self.path == "/api/save-preset":
            save_preset(body.get("key", "custom"), body.get("preset", {}))
            self._json({"success": True})

        # Timeline editing
        elif self.path == "/api/timeline/move-clip":
            self._edit_timeline("move", body)
        elif self.path == "/api/timeline/trim-clip":
            self._edit_timeline("trim", body)
        elif self.path == "/api/timeline/add-keyframe":
            self._edit_timeline("add_keyframe", body)
        elif self.path == "/api/timeline/remove-clip":
            self._edit_timeline("remove_clip", body)
        elif self.path == "/api/timeline/set-format":
            self._edit_timeline("set_format", body)
        elif self.path == "/api/timeline/undo":
            result = state_mgr.undo()
            if result:
                global timeline_data
                timeline_data = result
            self._json({"success": result is not None, "can_undo": state_mgr.can_undo, "can_redo": state_mgr.can_redo})
        elif self.path == "/api/timeline/redo":
            result = state_mgr.redo()
            if result:
                timeline_data = result
            self._json({"success": result is not None, "can_undo": state_mgr.can_undo, "can_redo": state_mgr.can_redo})

        # Updates
        elif self.path == "/api/update-check":
            self._json(UpdateManager().check_for_updates())
        elif self.path == "/api/update-apply":
            mgr = UpdateManager()
            info = mgr.check_for_updates()
            self._json(mgr.apply_update(info) if info.get("has_update") else {"message": "Atualizado"})
        elif self.path == "/api/update-rollback":
            self._json(UpdateManager().rollback())
        else:
            self._json({"error": "Not found"}, 404)

    def _get_timeline(self):
        global timeline_data
        if timeline_data:
            self._json({
                "timeline": timeline_data,
                "can_undo": state_mgr.can_undo,
                "can_redo": state_mgr.can_redo,
            })
        else:
            # Try load from disk
            for p in Path("output").glob("*/project_timeline.json"):
                data = json.loads(p.read_text(encoding="utf-8"))
                timeline_data = data
                self._json({"timeline": data, "can_undo": False, "can_redo": False})
                return
            self._json({"error": "No timeline"}, 404)

    def _edit_timeline(self, action: str, body: dict):
        global timeline_data
        if not timeline_data:
            self._json({"error": "No timeline loaded"}, 400)
            return

        from engine.timeline_builder import Timeline

        # Save state for undo
        state_mgr.set_state(timeline_data, action)

        tl = Timeline.from_dict(timeline_data)

        if action == "move":
            tl.move_clip(body.get("clip_id", ""), body.get("new_start", 0))
        elif action == "trim":
            tl.trim_clip(body.get("clip_id", ""), body.get("new_start"), body.get("new_end"))
        elif action == "remove_clip":
            clip_id = body.get("clip_id", "")
            for track in tl.tracks:
                track.remove_clip(clip_id)
        elif action == "set_format":
            tl.set_format(body.get("aspect", "9:16"))
        elif action == "add_keyframe":
            clip = tl.find_clip(body.get("clip_id", ""))
            if clip:
                prop = body.get("property", "scale")
                t = body.get("time", 0)
                val = body.get("value", 1.0)
                easing = body.get("easing", "ease_in_out")
                env = getattr(clip, prop, None)
                if env and hasattr(env, "add"):
                    env.add(t, val, easing)

        timeline_data = tl.to_dict()
        self._json({
            "success": True,
            "timeline": timeline_data,
            "can_undo": state_mgr.can_undo,
            "can_redo": state_mgr.can_redo,
        })

    def _process(self, body, preview_only):
        def run():
            global timeline_data
            state["status"] = "processing"
            state["progress"] = 0
            state["error"] = None
            try:
                pipeline = VclipPipeline(client_preset=body.get("client"))
                results = pipeline.process(
                    input_video=body.get("input_video", ""),
                    output_dir=body.get("output_dir", "output"),
                    decupagem_path=body.get("decupagem"),
                    music_path=body.get("music"),
                    skip_silence=body.get("skip_silence", False),
                    skip_reframe=body.get("skip_reframe", False),
                    skip_subtitles=body.get("skip_subtitles", False),
                    skip_overlay=body.get("skip_overlay", False),
                    dynamic_reframe=body.get("dynamic_reframe", False),
                    max_clips=body.get("max_clips"),
                    overlay_path=body.get("overlay_path"),
                    preview_only=preview_only,
                    aspect_ratio=body.get("aspect_ratio", "9:16"),
                )
                # Convert pipeline project to Timeline format
                if pipeline.project:
                    timeline_data = pipeline.project
                    state_mgr.set_state(timeline_data, "process")
                state["status"] = "done"
                state["progress"] = 100
            except Exception as e:
                state["status"] = "error"
                state["error"] = str(e)
        _thread(run)
        self._json({"started": True})

    def _render(self, body):
        def run():
            state["status"] = "rendering"
            try:
                from engine.render_engine import RenderEngine
                renderer = RenderEngine()
                out = body.get("output_path", "output/render/rendered.mp4")
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                renderer.render(
                    timeline_data or {},
                    out,
                    progress_cb=lambda p: state.update({"progress": int(p * 100)}),
                )
                state["status"] = "done"
                state["progress"] = 100
            except Exception as e:
                state["status"] = "error"
                state["error"] = str(e)
        _thread(run)
        self._json({"started": True})

    def _export(self, body):
        def run():
            state["status"] = "exporting"
            try:
                from engine.export_engine import ExportEngine
                exp = ExportEngine()
                clips = body.get("clips", [])
                out_dir = Path(body.get("output_dir", "output/export"))
                out_dir.mkdir(parents=True, exist_ok=True)
                for i, clip in enumerate(clips, 1):
                    exp.export(clip["path"], str(out_dir / f"vclip_{i:03d}.mp4"),
                               preset_name=body.get("export_preset", "custom"),
                               music_path=body.get("music"))
                state["status"] = "done"
            except Exception as e:
                state["status"] = "error"
                state["error"] = str(e)
        _thread(run)
        self._json({"started": True})

    def _transcribe(self, body):
        def run():
            state["status"] = "transcribing"
            try:
                result = TranscriptionEngine().transcribe(body.get("input_video", ""))
                state["transcription"] = result
                state["status"] = "done"
            except Exception as e:
                state["status"] = "error"; state["error"] = str(e)
        _thread(run)
        self._json({"started": True})

    def _learn(self, body):
        def run():
            state["status"] = "learning"
            try:
                learner = FolderLearner()
                profile = learner.learn_from_folder(body.get("folder_path", ""), body.get("client_name", "default"))
                learner.save_profile(client_name=body.get("client_name"))
                state["status"] = "done"
            except Exception as e:
                state["status"] = "error"; state["error"] = str(e)
        _thread(run)
        self._json({"started": True})

    def _serve_file(self, file_path):
        p = Path(file_path)
        if not p.exists():
            self._json({"error": "Not found"}, 404); return
        ct = {".mp4":"video/mp4",".png":"image/png",".jpg":"image/jpeg",
              ".json":"application/json",".srt":"text/plain",".ass":"text/plain"
              }.get(p.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(p, "rb") as f:
            self.wfile.write(f.read())

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        try: return json.loads(self.rfile.read(length).decode("utf-8"))
        except: return {}

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *a): pass


def start_server(port=9876):
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"[API] Vclip Engine v2 em http://127.0.0.1:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__ == "__main__":
    start_server()
