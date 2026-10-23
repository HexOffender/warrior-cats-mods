# wcmods SDK

The mod manager is built from **sections**. Each section handles one kind of mod content.
The built-in ones are replacement files, game data, palettes, controls, mouse look and save edits. A mod
can add its own section in two halves, both built on the shared library:

| Half | File in the mod folder | Runs in | Built on |
|---|---|---|---|
| Build step | `section.py` | `wcmods build` / `install` | `wcmods.sdk` (Python) |
| Studio page | `studio/section.js` | `wcmods studio`, in your browser | `studio/lib/wc.js` |

Both halves only run when `"allow_code_mods": true` is set in `wcmods.json`, because they
are code. Without it, the build warns and skips them. Everything else in the mod still works.

A complete example lives in [`examples/faster-run`](../examples/faster-run). To try it, copy it
into `mods/` and allow code mods.

## Mod folder

```
mods/my-mod/
  mod.json            {"name", "description", "enabled", "priority",
                       "studio_title" (nav label), "studio_files" (["my-settings.json"])}
  files/Wrc/...       replacement game files            -> section "files"
  data.json           CSV cell edits                    -> section "data"
  palette.json        colour palettes                   -> section "palettes"
  controls.json       key and button remaps             -> section "controls"
  mouselook.json      mouse look settings               -> section "mouselook"
  save.json           save edits                        -> section "save"
  section.py          your own build step               (code mod)
  studio/section.js   your own studio page              (code mod)
```

## Python: `wcmods.sdk`

```python
from wcmods.sdk import Section

class MySection(Section):
    id = "my-section"          # unique; shown in build reports
    title = "My section"
    files = ("my-settings.json",)   # the section runs for mods that have any of these

    def collect(self, mod, ctx):
        # Read and validate this mod's files. Raise ValueError for mistakes the user
        # should fix: the build reports it and skips just this mod.
        return self.read_json(mod, "my-settings.json")

    def build(self, ctx, items):
        # items: [(mod, data)] for every enabled mod, lowest priority first.
        ...
```

Sections run independently. If `build` raises, everything that section added is rolled back,
the build report marks it FAILED, and the other sections carry on.

### BuildContext

| Call | Does |
|---|---|
| `ctx.read_game_file(path)` | Bytes of any game file (pak or IoStore, Oodle handled), e.g. `"Wrc/Config/DefaultGame.ini"` |
| `ctx.read_data_table("TuningData.csv")` | Text of a runtime CSV under `Gameplay/DataTables/NonAsset/` |
| `ctx.edit_csv(name, edits, source=mod.id)` | Queue cell edits; they merge with every other section's edits to the same table |
| `ctx.add_file(path, data, source=mod.id)` | Add or replace a loose file in the mod pak |
| `ctx.patch_package(path, data)` | Replace a cooked `.uasset` with patched bytes of the same layout (goes into the IoStore mod container) |
| `ctx.add_ue4ss_mod(name, {"Scripts/main.lua": text})` | Ship a UE4SS Lua mod; installed and registered only when UE4SS is present |
| `ctx.edit_save(path, value)` | Set an existing save value on install, e.g. `"0/GameplayProgression/Level"` |
| `ctx.add_save_key(object_path, key, value)` | Add a key to a save object, e.g. a new inventory item |
| `ctx.warn(msg)` / `ctx.log(msg)` / `ctx.note(key, value)` | Report to the user / the build log / the build manifest |
| `ctx.game`, `ctx.cfg` | The game reader (`find`, `exists`, `data_tables`) and the tool's configuration |

CSV edits use `{row: {column: value}}`. `"*"` means every row, `"x1.5"` multiplies the game's
number, and key/value tables like `TuningData.csv` accept `{row: value}`. Save paths use `/`,
because the game's keys contain dots. They start inside the save's account object: `Shared/...`
for shared data, and `0/...` for cat slot 0.

Helpers you can import: `wcmods.csvdata` (format-preserving CSV editing), `wcmods.savejson`
(format-preserving save JSON), `wcmods.colors`, `wcmods.palettes`, `wcmods.eyeatlas`,
`wcmods.gamefiles`.

## JavaScript: `studio/lib/wc.js`

A studio page is an ES module whose default export has a `mount(root, wc)` function:

```js
export default {
  title: "My page",
  async mount(root, wc) {
    const r = await wc.api.get("/mods/my-mod/file/my-settings.json");
    root.append(wc.el("h1", { text: "My page" }));
    return { unmount() {} };   // optional
  },
};
```

Each page is loaded only when it's opened, and a page that throws shows an error card without
affecting the others.

| Export | What it gives you |
|---|---|
| `api.get/post/put/patch/del(path)` | The studio API (token handled). Routes are listed below |
| `el(tag, attrs, ...children)`, `$`, `clear` | Small DOM helpers |
| `toast(msg, "bad"?)`, `confirmButton(label, armedLabel, fn)` | Feedback, and two-step confirm |
| `modTarget({file, defaultId, defaultName, onLoad, getValue})` | The "Editing mod: … Save to mod" bar the built-in pages use |
| `codePanel(title)` | A copyable JSON preview |
| `color` | sRGB/linear conversion, HSL, `mood(hex, "vivid"\|"pastel"\|"moonlit"\|"ember")` |
| `input` | Browser key/mouse/gamepad to Unreal key names, plus Xbox/PlayStation/Switch labels |
| `bus.on/emit` | Page-to-page events: `mods-changed`, `installed`, `run-task` |
| `getPath(obj, "a/b/c")` | Read a save path |

API routes: `GET /info`, `GET|POST /mods`, `PATCH /mods/<id>`,
`GET|PUT|DELETE /mods/<id>/file/<name>` (the built-in files plus the mod's `studio_files`),
`POST /build`, `/install`, `/uninstall`, `GET /backups`, `POST /backup`, `/restore`,
`GET /game/eyes`, `/game/tables`, `/game/bindings`, `/game/data`, `/game/data/<table>`, `/save`.

The server listens on 127.0.0.1 only, and every API call needs the per-run token that the page
gets when it loads. Other websites therefore can't drive it.
