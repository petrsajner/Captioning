"""Data folder next to the program and the one-time move from the pre-0.1.13 per-user folder."""

import json
import msvcrt
import sys

import pytest

from captioning import paths
from captioning.runtime import Runtime


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """A built program in tmp/program and old data in tmp/legacy, with no data-folder override."""
    program, legacy = tmp_path / "program", tmp_path / "legacy"
    program.mkdir()
    (legacy / "runtime" / "models").mkdir(parents=True)
    (legacy / "logs").mkdir()
    (legacy / "settings.json").write_text('{"trigger": "ohwx"}', encoding="utf-8")
    (legacy / "keys.json").write_text("{}", encoding="utf-8")
    (legacy / "session.json").write_text("[]", encoding="utf-8")
    (legacy / "logs" / "generation.jsonl").write_text("{}\n", encoding="utf-8")
    (legacy / "runtime" / "models" / "model.gguf").write_bytes(b"weights")
    monkeypatch.delenv("CAPTION_STUDIO_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths, "program_directory", lambda: program)
    monkeypatch.setattr(paths, "legacy_directory", lambda: legacy)
    return program / "data", legacy


def test_override_wins_and_nothing_moves(layout, tmp_path, monkeypatch):
    target, legacy = layout
    monkeypatch.setenv("CAPTION_STUDIO_DATA_DIR", str(tmp_path / "isolated"))
    assert paths.prepare_data_directory() == (tmp_path / "isolated", [])
    assert (legacy / "settings.json").exists() and not target.exists()


def test_same_drive_moves_everything_once(layout):
    target, legacy = layout
    root, notices = paths.prepare_data_directory()
    assert root == target and not legacy.exists()
    assert json.loads((target / "settings.json").read_text(encoding="utf-8")) == {"trigger": "ohwx"}
    assert (target / "runtime" / "models" / "model.gguf").read_bytes() == b"weights"
    assert notices == [f"Caption Studio now keeps its data next to the program: {target}"]
    legacy.mkdir()
    (legacy / "settings.json").write_text("{}", encoding="utf-8")
    assert paths.prepare_data_directory() == (target, [])  # an existing data folder is never replaced
    assert (legacy / "settings.json").exists()


def test_other_drive_moves_personal_files_and_explains_the_model(layout, monkeypatch):
    target, legacy = layout
    monkeypatch.setattr(paths, "_same_volume", lambda a, b: False)
    root, notices = paths.prepare_data_directory()
    assert root == target
    assert {p.name for p in target.iterdir()} == {"settings.json", "keys.json", "session.json", "logs"}
    assert {p.name for p in legacy.iterdir()} == {"runtime"}
    assert str(legacy / "runtime") in notices[0] and str(target) in notices[0]


def test_failed_copy_leaves_old_data_complete(layout, monkeypatch):
    target, legacy = layout
    monkeypatch.setattr(paths, "_same_volume", lambda a, b: False)
    copies = []

    def failing_copy(source, destination):
        copies.append(source)
        if len(copies) == 2:
            raise OSError("disk full")
        return destination

    monkeypatch.setattr(paths.shutil, "copy2", failing_copy)
    assert paths.prepare_data_directory() == (legacy, [])
    assert {p.name for p in legacy.iterdir()} == {"settings.json", "keys.json", "session.json", "logs", "runtime"}
    assert list(target.iterdir()) == []


def test_running_older_version_keeps_its_folder(layout):
    target, legacy = layout
    with (legacy / "instance.lock").open("a+b") as lock:
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        assert paths.prepare_data_directory() == (legacy, [])
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    assert (legacy / "settings.json").exists()


def test_source_checkout_never_adopts_installed_data(layout, monkeypatch):
    target, legacy = layout
    monkeypatch.setattr(sys, "frozen", False)
    assert paths.prepare_data_directory() == (target, [])
    assert (legacy / "settings.json").exists() and list(target.iterdir()) == []


def test_read_only_program_folder_falls_back_with_a_notice(layout, monkeypatch):
    target, legacy = layout
    monkeypatch.setattr(paths, "_writable", lambda folder: False)
    root, notices = paths.prepare_data_directory()
    assert root == legacy and notices == [f"The program folder cannot be written to, so data is kept in {legacy}."]


def test_verified_models_stay_verified_after_the_data_folder_moves(tmp_path):
    old = tmp_path / "old"
    model = old / "runtime" / "models" / "model.gguf"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"weights")
    stat = model.stat()
    # A cache written before 0.1.13 used absolute paths.
    (old / "runtime" / "verified.json").write_text(json.dumps({str(model): ["sha", 7, stat.st_mtime_ns]}), "utf-8")
    new = tmp_path / "program" / "data"
    new.parent.mkdir()
    old.rename(new)
    runtime = Runtime(new)
    assert runtime.valid_file(new / "runtime" / "models" / "model.gguf", "sha", 7)
