# Plans for the Clan Mod Studio overhaul

These plans come from an audit of every studio page and subsystem on 2026-10-28: one reader per area traced each
feature from its page through the API to what reaches the game, a skeptic checked every high and medium bug claim
(166 of 174 held), and a planner wrote each plan from the maps and the verdicts, with a second pass that checked it
against the code. The studio's user is a creative person with no technical background, so every plan is judged
against them: what they can do, what goes wrong, and how they can tell a change reached the game.

Each plan has the same shape: what the feature is for, where it stands (what works and how that was verified, what
is half finished, the confirmed bugs with file and line), what a creator should be able to do, the ordered steps with
their tests and docs, what is deliberately not planned (and why), and the decisions left for the owner.

| Plan | Covers |
|---|---|
| [mods-setup.md](mods-setup.md) | Getting set up, the Mods page, the companion mods (Menu pages, Sandbox mode, Creator palettes, Emote wheel), versions, the game-update policy, Mod packs, Settings and repair |
| [palettes-cat.md](palettes-cat.md) | Looks: the Palettes and Your cat pages |
| [names.md](names.md) | Words: the Names page, and rewriting what cats say |
| [items-animations.md](items-animations.md) | Things: the Items and Animations pages, including animations without Blender |
| [story.md](story.md) | Stories: the Characters and Questlines pages with Sandbox mode |
| [data-save.md](data-save.md) | Numbers: the Game data and Save pages |
| [controls.md](controls.md) | Controls: the Controls page and remapping |
| [console-lua.md](console-lua.md) | Scripts, the Console page and the in-game runtime |
| [docs-guide.md](docs-guide.md) | The creator guide ("Making mods without code") and the docs |
| [re-roadmap.md](re-roadmap.md) | Reverse-engineering roadmap: the facts about the game that would unlock the next creator features |

## Work the plans build on

Three pull requests came first and every plan assumes them:

- the test harness (`claude/studio-tests`): fixtures that drive the studio's API over temporary folders, tests of
  the HTTP handler, a dependency-free headless-browser driver for the pages, JavaScript unit tests, and CI with Node;
- the look (`claude/studio-look`): "Leaf and Bark", a forest-floor theme by day and a moonlit one by night, with a
  theme switch, per-page stylesheets and a page-header helper;
- the shell (`claude/studio-shell`): mistakes shown when a page saves instead of at Apply, no lost edits, progress
  and a plain-words summary in the log, a Last apply button, errors reworded, a Restart button after an update, a
  tolerant settings file, and help panels inside the studio.

The feature pull requests are cut from the shell branch and can be merged in any order after it.
