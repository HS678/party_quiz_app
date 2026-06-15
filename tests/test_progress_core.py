from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PROGRESS_FILE = ROOT / "data" / "progress.json"
EMPTY_PROGRESS = {"random": {"single": {}, "multiple": {}}, "sequential": {}, "exam": {}}


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def load_app_with_fake_streamlit():
    fake_st = types.SimpleNamespace(session_state=SessionState())
    sys.modules["streamlit"] = fake_st
    spec = importlib.util.spec_from_file_location("quiz_app_for_tests", APP)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, fake_st


def init_state(app, fake_st):
    fake_st.session_state.questions = app.load_questions()
    fake_st.session_state.qmap = {app.qkey(q): q for q in fake_st.session_state.questions}
    fake_st.session_state.progress = app.load_progress()


def reset_progress_file():
    PROGRESS_FILE.write_text(json.dumps(EMPTY_PROGRESS, ensure_ascii=False, indent=2), encoding="utf-8")


def test_reset_random_practice_saves_progress_file():
    reset_progress_file()
    app, fake_st = load_app_with_fake_streamlit()
    init_state(app, fake_st)
    app.reset_random_practice("single")
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    assert progress["random"]["single"]["current_index"] == 0
    assert len(progress["random"]["single"]["order"]) == 306


def test_reset_sequential_practice_saves_progress_file():
    reset_progress_file()
    app, fake_st = load_app_with_fake_streamlit()
    init_state(app, fake_st)
    app.reset_sequential_practice()
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    assert progress["sequential"]["current_index"] == 0
    assert progress["sequential"]["order"][0] == "single:1"
    assert progress["sequential"]["order"][305] == "single:306"
    assert progress["sequential"]["order"][306] == "multiple:1"


def test_reset_exam_saves_single_first_multiple_second_progress_file():
    reset_progress_file()
    app, fake_st = load_app_with_fake_streamlit()
    init_state(app, fake_st)
    app.reset_exam()
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    order = progress["exam"]["order"]
    assert len(order) == 100
    assert all(k.startswith("single:") for k in order[:70])
    assert all(k.startswith("multiple:") for k in order[70:])
