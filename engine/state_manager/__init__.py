"""Vclip - State Manager: undo/redo e persistência de estado."""

import json
import copy
import time
from pathlib import Path
from typing import Any, Optional


class StateManager:
    """Gerencia estado do projeto com undo/redo."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._current_state: dict = {}
        self._log: list = []

    def set_state(self, state: dict, action: str = ""):
        """Salva estado atual no undo stack e define novo estado."""
        if self._current_state:
            self._undo_stack.append({
                "state": copy.deepcopy(self._current_state),
                "action": action,
                "timestamp": time.time(),
            })
            if len(self._undo_stack) > self.max_history:
                self._undo_stack.pop(0)
        self._current_state = copy.deepcopy(state)
        self._redo_stack.clear()
        self._log.append({"action": action, "timestamp": time.time()})

    def undo(self) -> Optional[dict]:
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        self._redo_stack.append({
            "state": copy.deepcopy(self._current_state),
            "action": "undo",
            "timestamp": time.time(),
        })
        self._current_state = entry["state"]
        self._log.append({"action": f"undo: {entry['action']}", "timestamp": time.time()})
        return self._current_state

    def redo(self) -> Optional[dict]:
        if not self._redo_stack:
            return None
        entry = self._redo_stack.pop()
        self._undo_stack.append({
            "state": copy.deepcopy(self._current_state),
            "action": "redo",
            "timestamp": time.time(),
        })
        self._current_state = entry["state"]
        self._log.append({"action": "redo", "timestamp": time.time()})
        return self._current_state

    @property
    def current(self) -> dict:
        return self._current_state

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def history(self) -> list:
        return self._log[-50:]

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({
            "current": self._current_state,
            "log": self._log[-50:],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str):
        if Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self._current_state = data.get("current", {})
            self._log = data.get("log", [])
