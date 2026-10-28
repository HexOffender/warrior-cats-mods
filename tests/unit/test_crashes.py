"""The game's crash reports (wcmods/crashes.py) and the studio's GET /crash: a report read whatever its encoding,
the newest one after a time, and which C++ mod a crash was in. The reports are made-up ones in the layout
Unreal writes (CrashContext.runtime-xml), in a folder of the test's own (WCMODS_CRASHES)."""
import datetime
import os
import time

import pytest

from wcmods import crashes

from unit_helpers import make_mod

REPORT = """<?xml version="1.0" encoding="UTF-8"?>
<FGenericCrashContext>
  <RuntimeProperties>
    <CrashType>Crash</CrashType>
    <ErrorMessage>Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0000000000000010</ErrorMessage>
    <CallStack>{stack}</CallStack>
  </RuntimeProperties>
</FGenericCrashContext>
"""


@pytest.fixture
def crash_dir(tmp_path, monkeypatch):
    folder = tmp_path / "Crashes"
    folder.mkdir()
    monkeypatch.setenv("WCMODS_CRASHES", str(folder))
    return folder


def report(folder, name, stack="Wrc_Win64_Shipping!UnknownFunction []", encoding="utf-8", when=None):
    d = folder / name
    d.mkdir()
    path = d / "CrashContext.runtime-xml"
    text = REPORT.format(stack=stack)
    path.write_bytes(text.encode("utf-16") if encoding == "utf-16" else text.encode(encoding))
    if when is not None:
        os.utime(path, (when, when))
    return str(path)


def call(st, path):
    return st.api("GET", [p for p in path.split("/") if p], {}, None, None)


def test_a_utf16_crash_report_is_read(crash_dir):
    for enc in ("utf-16", "utf-8-sig", "utf-8", "cp1252"):
        crash = crashes.read(report(crash_dir, f"c-{enc}", encoding=enc))
        assert crash["type"] == "Crash" and crash["error"].startswith("Unhandled Exception: EXCEPTION_ACCESS_VIOLATION"), enc
    broken = crash_dir / "broken"
    broken.mkdir()
    (broken / "CrashContext.runtime-xml").write_text("<not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="the crash report couldn't be read"):
        crashes.read(str(broken / "CrashContext.runtime-xml"))
    assert crashes.readout(str(broken / "CrashContext.runtime-xml"), [], None).startswith("the crash report couldn't be read")


def test_latest_after_a_time(crash_dir):
    now = time.time()
    report(crash_dir, "old", when=now - 3600)
    new = report(crash_dir, "new", when=now - 60)
    assert crashes.latest() == new
    assert crashes.latest(after=now - 120) == new
    assert crashes.latest(after=now - 30) is None


def test_crash_route_is_empty_without_a_crash(studio, crash_dir):
    assert call(studio, "crash") == {"crash": None}
    report(crash_dir, "before", when=time.time() - 3600)
    cfg = studio.ctx.cfg
    cfg.data["installed"] = {"mods": [], "built": datetime.datetime.now().isoformat(timespec="seconds")}
    cfg.save()
    assert call(studio, "crash") == {"crash": None}   # older than the last Apply: not this one's
    report(crash_dir, "after", when=time.time() + 60)
    c = call(studio, "crash")["crash"]
    assert c["message"].startswith("Unhandled Exception") and c["mod"] is None and "no C++ mod on the stack" in c["readout"]


def test_a_cpp_frame_names_the_mod(studio, crash_dir):
    folder = make_mod(studio, "my-tabs", {"name": "My tabs"}, {"cpp/src/main.cpp": "// the mod"})
    source = os.path.join(folder, "cpp", "src", "main.cpp")
    stack = f"main!MyTabs::on_draw() [{source}:42]\nWrc_Win64_Shipping!UnknownFunction []"
    report(crash_dir, "cpp", stack=stack, when=time.time() + 60)
    c = call(studio, "crash")["crash"]
    assert c["mod"] == "my-tabs" and c["mod_name"] == "My tabs" and c["where"] == "cpp/src/main.cpp:42, MyTabs::on_draw()"
    assert "in the C++ mod my-tabs" in c["readout"]
