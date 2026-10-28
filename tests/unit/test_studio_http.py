"""Clan Mod Studio's HTTP handler (wcmods/studio.py, make_handler), on a port of its own: the token and Host
checks, what a body may be, uploads, how exceptions become statuses, the static files and a download's
headers. A real server on 127.0.0.1, as selftest._onboarding_edges runs one."""
import http.client
import json
import os
import tempfile
import threading
import zipfile

import pytest

from wcmods import studio as studio_mod
from wcmods.studio import MAX_UPLOAD, NO_GAME

from conftest import REPO, make_mod


@pytest.fixture
def server(studio):
    """The studio served on a free port; yields an `ask` helper and the port, then stops it."""
    srv = studio_mod._Server(("127.0.0.1", 0), None)
    port = srv.server_address[1]
    srv.RequestHandlerClass = studio_mod.make_handler(studio, port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def ask(path, method="GET", body=None, headers=None, token=True, host=None):
        """(status, answer, headers): `body` is sent as JSON when it's a dict or list, as is when bytes or text."""
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        h = {"Host": host or f"127.0.0.1:{port}"}
        if token:
            h["X-WC-Token"] = studio.token if token is True else token
        data = None
        if body is not None:
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
            data = data.encode() if isinstance(data, str) else data
            h.setdefault("Content-Type", "application/json")
        h.update(headers or {})
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        raw, answer = r.read(), None
        if r.getheader("Content-Type", "").startswith("application/json"):
            answer = json.loads(raw)
        conn.close()
        return r.status, raw if answer is None else answer, dict(r.getheaders())

    ask.port = port
    yield ask
    srv.shutdown()
    srv.server_close()


def test_the_api_needs_the_studios_token(server):
    assert server("/api/info", token=False)[0] == 403
    status, answer, _ = server("/api/info", token="wrong")
    assert status == 403 and "missing or wrong studio token" in answer["error"]
    status, answer, headers = server("/api/info")
    assert status == 200 and answer["game_dir"] is None
    assert headers["Cache-Control"] == "no-store" and headers["X-Content-Type-Options"] == "nosniff"


def test_another_host_is_refused_even_with_the_token(server):
    for host in ("evil.example", f"evil.example:{server.port}", "127.0.0.1:1", "localhost"):
        status, answer, _ = server("/api/info", host=host)
        assert (status, answer) == (403, {"error": "wrong host"}), host
    assert server("/", host=f"localhost:{server.port}")[0] == 200


def test_a_body_has_to_be_a_json_object(server):
    status, answer, _ = server("/api/mods", "POST", "{not json")
    assert status == 400 and answer["error"].startswith("request body isn't valid JSON")
    status, answer, _ = server("/api/mods", "POST", [1, 2])
    assert (status, answer) == (400, {"error": "request body must be a JSON object"})
    assert server("/api/mods", "POST", "null")[0] == 400
    status, answer, _ = server("/api/mods", "POST", b"\xff\xfe", headers={"Content-Type": "application/json"})
    assert status == 400 and "isn't valid JSON" in answer["error"]
    status, answer, _ = server("/api/mods", "POST", {"id": "made"})
    assert status == 200 and answer["id"] == "made"


def test_a_key_the_request_left_out_is_a_400_with_a_sentence(server):
    status, answer, _ = server("/api/mods", "POST", {})
    assert (status, answer) == (400, {"error": 'the request needs "id"'})
    status, answer, _ = server("/api/mods/restore", "POST", {})
    assert (status, answer) == (400, {"error": 'the request needs "name"'})
    status, answer, _ = server("/api/restore", "POST", {"name": ["x"]})
    assert (status, answer) == (400, {"error": '"name" should be text'})


def test_exceptions_become_statuses_without_a_traceback_in_the_answer(server, studio, capfd):
    def api(method, parts, body, query=None, upload=None):
        raise {"lookup": LookupError("no such thing"), "forbidden": PermissionError("not allowed"),
               "value": ValueError("that's wrong"), "runtime": RuntimeError("close the game"),
               "exit": SystemExit("Couldn't find the game"), "key": KeyError("game file not found: x.csv"),
               "zip": zipfile.BadZipFile("bad"), "other": ZeroDivisionError("division by zero")}[parts[0]]
    studio.api = api
    assert server("/api/lookup") == (404, {"error": "no such thing"}, server("/api/lookup")[2])
    assert server("/api/forbidden")[:2] == (403, {"error": "not allowed"})
    assert server("/api/value")[:2] == (400, {"error": "that's wrong"})
    assert server("/api/runtime")[:2] == (400, {"error": "close the game"})
    assert server("/api/exit")[:2] == (400, {"error": NO_GAME})
    assert server("/api/key")[:2] == (400, {"error": "game file not found: x.csv"})
    assert server("/api/zip")[:2] == (400, {"error": "that isn't a .zip file (or it's damaged)"})
    status, answer, _ = server("/api/other")
    assert (status, answer) == (500, {"error": "ZeroDivisionError: division by zero"})
    assert "Traceback" not in json.dumps(answer) and "Traceback" in capfd.readouterr().err   # the console gets it


def test_with_a_game_folder_a_system_exit_keeps_its_own_words(server, studio, fake_game):
    studio.api = lambda *a, **k: (_ for _ in ()).throw(SystemExit("the game's folder has moved"))
    assert server("/api/anything")[:2] == (400, {"error": "the game's folder has moved"})


def test_an_upload_over_the_limit_is_refused_before_it_is_read_and_leaves_no_temp_file(server, studio, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=20)
    conn.putrequest("POST", "/api/mods/add?step=preview")
    conn.putheader("Host", f"127.0.0.1:{server.port}")
    conn.putheader("X-WC-Token", studio.token)
    conn.putheader("Content-Type", "application/zip")
    conn.putheader("Content-Length", str(MAX_UPLOAD + 1))
    conn.endheaders()
    try:
        conn.send(b"PK\x03\x04 a few bytes of what would be a huge file")
    except OSError:
        pass   # the server answered without reading it, and may have closed already
    r = conn.getresponse()
    assert r.status == 413 and "over" in json.loads(r.read())["error"]
    conn.close()
    assert [f for f in os.listdir(tmp_path) if f.startswith("wcmods-upload-")] == []


def test_an_upload_is_read_from_a_temp_file_that_is_removed_after(server, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    z = tmp_path / "cool.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("cool/mod.json", json.dumps({"name": "Cool"}))
    status, answer, _ = server("/api/mods/add?step=preview&name=cool.zip", "POST", z.read_bytes(),
                               headers={"Content-Type": "application/zip"})
    assert status == 200 and answer["mods"][0]["id"] == "cool"
    status, answer, _ = server("/api/mods/add?step=preview&name=cool.zip", "POST", b"not a zip",
                               headers={"Content-Type": "application/octet-stream"})
    assert (status, answer) == (400, {"error": "that isn't a .zip file (or it's damaged)"})
    assert [f for f in os.listdir(tmp_path) if f.startswith("wcmods-upload-")] == []


def test_the_page_and_its_files_are_served_and_nothing_outside_them(server, studio):
    status, html, headers = server("/")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert f'<meta name="wc-token" content="{studio.token}">'.encode() in html and b"{{WC_TOKEN}}" not in html
    assert server("/index.html")[0] == 200
    status, js, headers = server("/studio/app.js")
    assert status == 200 and headers["Content-Type"] == "text/javascript; charset=utf-8" and b"refreshStatus" in js
    assert server("/studio/styles.css")[2]["Content-Type"].startswith("text/css")
    for path in ("/studio/../wcmods/config.py", "/studio/%2e%2e/wcmods/config.py", "/studio/", "/studio/nope.js",
                 "/wcmods/config.py", "/nope", "/mods/x/studio/section.js"):
        assert server(path)[0] == 404, path
    assert server("/", "POST")[:2] == (405, {"error": "method not allowed"})
    assert server("/studio/app.js", "DELETE")[0] == 405


def test_a_mods_own_page_is_served_only_with_code_mods_allowed(server, studio):
    make_mod(studio, "paged", files={"studio/section.js": "export default {}", "studio/notes.txt": "x", "secret.json": "{}"})
    assert server("/mods/paged/studio/section.js")[0] == 404
    assert server("/api/settings", "PATCH", {"allow_code_mods": True})[0] == 200
    status, js, headers = server("/mods/paged/studio/section.js")
    assert status == 200 and js == b"export default {}" and headers["Content-Type"] == "text/javascript; charset=utf-8"
    assert server("/mods/paged/studio/notes.txt")[0] == 200
    assert server("/mods/paged/studio/../secret.json")[0] == 404 and server("/mods/paged/secret.json")[0] == 404


def test_a_zip_download_names_its_file(server, studio):
    make_mod(studio, "share-me", {"version": "1.0"})
    status, data, headers = server("/api/mods/share-me/zip")
    assert status == 200 and headers["Content-Type"] == "application/zip"
    assert headers["Content-Disposition"] == 'attachment; filename="share-me-1.0.zip"'
    assert headers["Content-Length"] == str(len(data)) and zipfile.is_zipfile(__import__("io").BytesIO(data))
    assert server("/api/mods/nope/zip")[:2] == (404, {"error": "no mod named nope"})


def test_eight_saves_of_one_file_at_once_all_succeed_and_leave_valid_json(server, studio):
    make_mod(studio, "mine")
    texts = [json.dumps({"n": i, "pad": "x" * (i * 50)}) for i in range(8)]
    results = [None] * 8

    def put(i):
        results[i] = server("/api/mods/mine/file/data.json", "PUT", {"text": texts[i]})[0]
    threads = [threading.Thread(target=put, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [200] * 8
    with open(os.path.join(studio.ctx.mods_root, "mine", "data.json"), encoding="utf-8") as f:
        saved = f.read()
    assert saved.rstrip("\n") in texts and json.loads(saved)["pad"] == "x" * (json.loads(saved)["n"] * 50)


def test_the_studio_folder_served_is_the_repositorys(studio):
    assert os.path.samefile(studio.static, os.path.join(REPO, "studio"))
