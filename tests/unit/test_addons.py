"""The mods that go with Clan Mod Studio (wcmods/addons.py): picking each one's .zip from its GitHub release,
adding every mod in it as it ships, updating with your settings and on/off kept, GitHub's trouble said in
words, and the studio's routes for them. GitHub is never asked: its answers are stood in for (a stub of
ue4ss.github_release and ue4ss.download, or WCMODS_RELEASES, a folder of .zips)."""
import json
import os
import shutil
import urllib.error
import urllib.request
import zipfile

import pytest

from wcmods import addons, cli, menupages, modzip, onboarding, ue4ss
from wcmods.mods import discover

from conftest import make_mod


def zip_of(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, (str, bytes)) else json.dumps(data))
    return str(path)


def call(st, method, path, body=None, query=None, upload=None):
    return st.api(method, [p for p in path.split("/") if p], {} if body is None else body, query, upload)


def sandbox_zip(path, version="0.4", settings=None):
    files = {"sandbox/mod.json": {"name": "Sandbox mode", "version": version}, "sandbox/scripts/main.lua": "-- sandbox"}
    if settings is not None:
        files["sandbox/settings.json"] = settings
    return zip_of(path, files)


def palettes_zip(path, version="1.2.0"):
    """As Creator palettes' tools/pack.py makes it: the mod, Coat presets (on) and themed palettes (off)."""
    files = {"creator-palettes/mod.json": {"name": "Creator palettes", "version": version, "enabled": True},
             "creator-palettes/scripts/main.lua": "-- pickers",
             "palette-coat-presets/mod.json": {"name": "Coat presets", "enabled": True, "wcmods": "0.4.0"},
             "palette-coat-presets/palette.json": {"coats": {}}}
    for theme in ("dark-forest", "pastel-kits", "vivid-clans"):
        files[f"palette-{theme}/mod.json"] = {"name": theme.replace("-", " ").title(), "enabled": False}
        files[f"palette-{theme}/palette.json"] = {"fur": {"1": "#123456"}}
    return zip_of(path, files)


def wheel_zip(path, version="1.0", key="T"):
    return zip_of(path, {"emote-wheel/mod.json": {"name": "Emote wheel", "version": version},
                         "emote-wheel/scripts/main.lua": "-- wheel",
                         "emote-wheel/settings.json": {"_help": f"v{version}", "key": key, "pause": True}})


@pytest.fixture
def github(monkeypatch, tmp_path):
    """GitHub stood in for: `releases` maps a repository to its latest release's tag and .zips ({name: a path
    on disk}), or to None for one with no release (GitHub's 404). Every question asked is in `asked`; every
    download in `downloads`."""
    class GitHub:
        releases, asked, downloads = {}, [], []
    gh = GitHub()

    def release(api, what, page, timeout=20):
        gh.asked.append(api)
        repo = api.split("/repos/")[1].rsplit("/releases", 1)[0]
        rel = gh.releases.get(repo)
        if rel is None:
            raise ue4ss.NoRelease(f"{what} has no release on GitHub yet ({page})")
        tag, files = rel
        return {"tag_name": tag, "assets": [{"name": n, "browser_download_url": f"https://example.invalid/{n}",
                                             "size": os.path.getsize(p)} for n, p in files.items()]}

    def download(asset, folder, timeout=60, limit=ue4ss.MAX_ZIP, what="UE4SS"):
        gh.downloads.append(asset["name"])
        for _, files in filter(None, gh.releases.values()):
            if asset["name"] in files:
                return shutil.copy(files[asset["name"]], os.path.join(folder, asset["name"]))
        raise RuntimeError(f"the {what} download failed (not found); try again")

    monkeypatch.setattr(ue4ss, "github_release", release)
    monkeypatch.setattr(ue4ss, "download", download)
    return gh


# ---------- the registry and its releases ----------
def test_the_sandbox_release_picks_the_mod_not_the_examples(github, tmp_path):
    github.releases["HexOffender/wcmods-sandbox"] = ("v0.4", {
        "sandbox-story-0.3.zip": zip_of(tmp_path / "a.zip", {"x/mod.json": {}}),
        "sandbox-welcome-0.2.zip": zip_of(tmp_path / "b.zip", {"y/mod.json": {}}),
        "sandbox-0.4.zip": sandbox_zip(tmp_path / "c.zip")})
    found = addons.find_release(addons.get("sandbox"))
    assert found["name"] == "sandbox-0.4.zip" and found["version"] == "0.4"
    assert found["page"] == "https://github.com/HexOffender/wcmods-sandbox/releases"


def test_every_addon_is_listed_once_with_its_words():
    ids = [a.id for a in addons.ADDONS]
    assert ids == ["menu-pages", "sandbox", "creator-palettes", "emote-wheel"] and len(set(ids)) == 4
    assert all(a.about and a.name and a.repo.startswith("HexOffender/") for a in addons.ADDONS)
    assert addons.find("nope") is None
    with pytest.raises(LookupError):
        addons.get("nope")


def test_creator_palettes_comes_with_coat_presets_on_and_the_themes_off(studio, github, tmp_path):
    github.releases["HexOffender/wcmods-creator-palettes"] = ("v1.2.0", {
        "creator-palettes-1.2.0.zip": palettes_zip(tmp_path / "p.zip")})
    done = addons.add(studio.ctx.cfg, "creator-palettes", log=lambda m: None)
    assert done["version"] == "1.2.0" and done["on"] is True and not done["unchanged"]
    on = {m.id: m.enabled for m in discover(studio.ctx.mods_root)}
    assert on == {"creator-palettes": True, "palette-coat-presets": True, "palette-dark-forest": False,
                  "palette-pastel-kits": False, "palette-vivid-clans": False}
    # The download is kept for the next add (or a preview's add), in the cache folder of your files.
    assert os.listdir(os.path.join(studio.ctx.cfg.data_dir, "cache", "downloads")) == ["creator-palettes-1.2.0.zip"]


def test_an_addon_equal_to_the_installed_version_is_unchanged(studio, github, tmp_path):
    github.releases["HexOffender/wcmods-sandbox"] = ("v0.4", {"sandbox-0.4.zip": sandbox_zip(tmp_path / "s.zip")})
    cfg = studio.ctx.cfg
    addons.add(cfg, "sandbox", log=lambda m: None)
    github.downloads.clear()
    again = addons.add(cfg, "sandbox", log=lambda m: None)
    assert again["unchanged"] and again["version"] == "0.4" and again["replaced"] is None
    assert github.downloads == [] and modzip.removed(cfg.backups_dir) == []   # nothing downloaded, nothing backed up


def test_github_trouble_names_the_addon_and_its_page_and_leaves_no_folder(studio, monkeypatch):
    def not_found(req, timeout=20):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", not_found)
    with pytest.raises(ue4ss.NoRelease) as e:
        addons.add(studio.ctx.cfg, "emote-wheel", log=lambda m: None)
    said = str(e.value)
    assert said.startswith("Emote wheel has no release yet; the owner of that mod has to publish one")
    assert "https://github.com/HexOffender/wcmods-emote-wheel/releases" in said
    mods_root = studio.ctx.mods_root
    assert not os.path.isdir(mods_root) or not [d for d in os.listdir(mods_root) if d.startswith("_adding-")]
    assert addons.latest(addons.get("emote-wheel"))["no_release"] is True

    def offline(req, timeout=20):
        raise urllib.error.URLError("no connection")
    monkeypatch.setattr(urllib.request, "urlopen", offline)
    with pytest.raises(RuntimeError, match="couldn't reach GitHub for Sandbox mode .*releases"):
        addons.add(studio.ctx.cfg, "sandbox", log=lambda m: None)


def test_a_zip_without_the_addon_is_refused_and_the_old_copy_kept(studio, tmp_path):
    cfg = studio.ctx.cfg
    addons.add(cfg, "sandbox", sandbox_zip(tmp_path / "sandbox-0.3.zip", "0.3"), log=lambda m: None)
    other = zip_of(tmp_path / "sandbox-0.5.zip", {"something-else/mod.json": {"name": "Something else"}})
    with pytest.raises(ValueError, match="doesn't have the Sandbox mode mod in it"):
        addons.add(cfg, "sandbox", other, log=lambda m: None)
    assert [(m.id, m.version) for m in discover(studio.ctx.mods_root)] == [("sandbox", "0.3")]
    assert modzip.removed(cfg.backups_dir) == []


def test_updating_keeps_off_and_settings(studio, tmp_path):
    cfg = studio.ctx.cfg
    addons.add(cfg, "emote-wheel", wheel_zip(tmp_path / "emote-wheel-1.0.zip"), log=lambda m: None)
    folder = os.path.join(studio.ctx.mods_root, "emote-wheel")
    with open(os.path.join(folder, "settings.json"), encoding="utf-8") as f:
        mine = json.load(f)
    mine["key"] = "B"
    with open(os.path.join(folder, "settings.json"), "w", encoding="utf-8") as f:
        json.dump(mine, f)
    discover(studio.ctx.mods_root)[0].set_enabled(False)
    done = addons.add(cfg, "emote-wheel", wheel_zip(tmp_path / "emote-wheel-1.1.zip", "1.1"), log=lambda m: None)
    assert done["version"] == "1.1" and done["replaced"] and done["on"] is False
    with open(os.path.join(folder, "settings.json"), encoding="utf-8") as f:
        assert json.load(f) == {"_help": "v1.1", "key": "B", "pause": True}   # your key, the new copy's help
    assert discover(studio.ctx.mods_root)[0].enabled is False


def test_adding_clears_not_now(studio, tmp_path):
    cfg = studio.ctx.cfg
    onboarding.skip_pages(cfg)
    assert cfg.data["skip_menu_pages"] is True
    pages = zip_of(tmp_path / "menu-pages-1.0.zip", {"menu-pages/mod.json": {"name": "Menu pages", "version": "1.0"},
                                                      "menu-pages/scripts/main.lua": ""})
    addons.add(cfg, "menu-pages", pages, log=lambda m: None)
    assert "skip_menu_pages" not in cfg.data
    with open(cfg.path, encoding="utf-8") as f:
        assert "skip_menu_pages" not in json.load(f)


def test_menu_pages_command_still_works(studio, tmp_path, capsys):
    pages = zip_of(tmp_path / "menu-pages-1.0.zip", {"menu-pages/mod.json": {"name": "Menu pages", "version": "1.0"},
                                                      "menu-pages/scripts/main.lua": "",
                                                      "menu-pages/settings.json": {"cheats": False}})
    studio.ctx.cfg.data["cheats"] = True   # from when the mod menu was wcmods' own
    studio.ctx.cfg.save()
    cli.cmd_menu_pages(studio.ctx, type("Args", (), {"zip": pages})())
    assert "Menu pages 1.0 is in your mods (menu-pages-1.0.zip)" in capsys.readouterr().out
    assert menupages.installed(studio.ctx.mods_root).version == "1.0" and menupages.cheats(studio.ctx.cfg) is True
    cli.cmd_addons(studio.ctx, type("Args", (), {"action": "add", "id": "menu-pages", "zip": pages})())
    assert "Menu pages 1.0 is in your mods" in capsys.readouterr().out


def test_add_zip_takes_a_per_mod_on_off(studio, tmp_path):
    z = zip_of(tmp_path / "three.zip", {"a/mod.json": {"name": "A"}, "b/mod.json": {"name": "B", "enabled": False},
                                         "c/mod.json": {"name": "C"}})
    done = modzip.add_zip(z, studio.ctx.mods_root, studio.ctx.backups, enable={"a": False, "b": True})
    assert {d["id"]: d["on"] for d in done} == {"a": False, "b": True, "c": True}   # c: as it ships
    assert {m.id: m.enabled for m in discover(studio.ctx.mods_root)} == {"a": False, "b": True, "c": True}
    folder = tmp_path / "folder"
    for i, shipped in (("d", False), ("e", True)):
        (folder / i).mkdir(parents=True)
        (folder / i / "mod.json").write_text(json.dumps({"name": i.upper(), "enabled": shipped}), encoding="utf-8")
    done = modzip.add_folder(str(folder), studio.ctx.mods_root, studio.ctx.backups, enable={"e": False})
    assert {d["id"]: d["on"] for d in done} == {"d": False, "e": False}


def test_the_releases_folder_stands_in_for_github(studio, monkeypatch, tmp_path):
    folder = tmp_path / "releases"
    folder.mkdir()
    sandbox_zip(folder / "sandbox-0.3.zip", "0.3")
    sandbox_zip(folder / "sandbox-0.10.zip", "0.10")
    zip_of(folder / "sandbox-story-0.9.zip", {"story/mod.json": {}})
    monkeypatch.setenv("WCMODS_RELEASES", str(folder))
    found = addons.find_release(addons.get("sandbox"))
    assert found["name"] == "sandbox-0.10.zip" and found["version"] == "0.10" and found["url"].startswith("file:")
    assert addons.add(studio.ctx.cfg, "sandbox", log=lambda m: None)["version"] == "0.10"
    assert addons.latest(addons.get("emote-wheel")) == {"no_release": True, "error": addons.no_release(addons.get("emote-wheel"))}


# ---------- the routes ----------
def test_get_addons_never_asks_github_unless_told_and_then_once_an_hour(studio, github, tmp_path):
    github.releases["HexOffender/wcmods-sandbox"] = ("v0.5", {"sandbox-0.5.zip": sandbox_zip(tmp_path / "s.zip", "0.5")})
    make_mod(studio, "sandbox", {"name": "Sandbox mode", "version": "0.4"}, {"scripts/main.lua": ""})
    r = call(studio, "GET", "addons")
    assert github.asked == [] and r["checked"] is None and r["code_allowed"] is False
    sandbox = next(a for a in r["addons"] if a["id"] == "sandbox")
    assert sandbox["installed"] and sandbox["version"] == "0.4" and sandbox["latest"] is None and sandbox["needs_code"]
    r = call(studio, "GET", "addons", query={"latest": "1"})
    assert len(github.asked) == 4 and r["checked"]
    by = {a["id"]: a for a in r["addons"]}
    assert by["sandbox"]["latest"] == "0.5" and by["sandbox"]["newer"] is True
    assert by["emote-wheel"]["no_release"] is True and "the owner of that mod has to publish one" in by["emote-wheel"]["error"]
    assert by["menu-pages"]["installed"] is False and by["menu-pages"]["newer"] is False
    call(studio, "GET", "addons", query={"latest": "1"})
    assert len(github.asked) == 4   # asked once, kept for the hour


def test_post_addon_adds_it_with_the_progress_and_notes_no_release(studio, github, tmp_path):
    github.releases["HexOffender/wcmods-sandbox"] = ("v0.4", {"sandbox-0.4.zip": sandbox_zip(tmp_path / "s.zip")})
    r = call(studio, "POST", "addons/sandbox", {"on": False})
    assert r["result"]["id"] == "sandbox" and r["result"]["on"] is False
    assert any("downloading sandbox-0.4.zip" in line for line in r["log"])
    assert [m.enabled for m in discover(studio.ctx.mods_root)] == [False]
    with pytest.raises(ue4ss.NoRelease, match="Creator palettes has no release yet"):
        call(studio, "POST", "addons/creator-palettes")
    by = {a["id"]: a for a in call(studio, "GET", "addons")["addons"]}
    assert by["creator-palettes"]["no_release"] is True and by["sandbox"]["latest"] == "0.4"
    with pytest.raises(ValueError, match='"on" should be true or false'):
        call(studio, "POST", "addons/sandbox", {"on": "yes"})
    with pytest.raises(LookupError):
        call(studio, "POST", "addons/nope")


def test_an_addons_preview_is_what_a_dropped_zip_would_show(studio, github, tmp_path):
    github.releases["HexOffender/wcmods-creator-palettes"] = ("v1.2.0", {
        "creator-palettes-1.2.0.zip": palettes_zip(tmp_path / "p.zip")})
    r = call(studio, "POST", "addons/creator-palettes/preview")
    assert r["version"] == "1.2.0" and r["name"] == "creator-palettes-1.2.0.zip" and r["code_allowed"] is False
    shipped = {m["id"]: m["enabled"] for m in r["mods"]}
    assert shipped["creator-palettes"] and shipped["palette-coat-presets"] and not shipped["palette-dark-forest"]
    assert discover(studio.ctx.mods_root) == []   # a preview adds nothing
    github.downloads.clear()
    call(studio, "POST", "addons/creator-palettes")
    assert github.downloads == []   # the add reads the preview's download


def test_the_setup_pages_route_is_still_menu_pages(studio, tmp_path):
    pages = zip_of(tmp_path / "menu-pages-1.1.zip", {"menu-pages/mod.json": {"name": "Menu pages", "version": "1.1"},
                                                      "menu-pages/scripts/main.lua": ""})
    r = call(studio, "POST", "setup/pages", upload=pages)
    assert r["result"]["version"] == "1.1" and r["result"]["from"] == "menu-pages-1.1.zip"
    assert call(studio, "POST", "setup/pages", {"skip": True}) == {"result": {"skipped": True}}
