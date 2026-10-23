"""Built-in sections and the loader for sections that mods ship themselves."""
import importlib.util
import inspect
import os

from ..sdk import Section
from .controls import ControlsSection
from .data import DataSection
from .files import FilesSection
from .palettes import PaletteSection
from .savedit import SaveSection

# Order matters only where outputs layer: replacement files first, CSV edits on top of them.
BUILTIN = (FilesSection, DataSection, PaletteSection, ControlsSection, SaveSection)


def load_sections(cfg, mods, log=print):
    """Built-in sections plus any section.py shipped by an enabled mod (if code mods are allowed)."""
    sections = [cls() for cls in BUILTIN]
    allow = bool(cfg.data.get("allow_code_mods"))
    skipped = []
    for mod in mods:
        path = os.path.join(mod.folder, "section.py")
        if not (mod.enabled and os.path.isfile(path)):
            continue
        if not allow:
            skipped.append(mod.id)
            continue
        spec = importlib.util.spec_from_file_location(f"wcmods_mod_{mod.id.replace('-', '_')}", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:  # a broken mod section must not stop the others
            log(f"  {mod.id}: section.py failed to load: {e}")
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Section) and obj is not Section and obj.__module__ == module.__name__:
                sec = obj()
                sec.owner = mod.id
                if not sec.id:
                    sec.id = mod.id
                if any(s.id == sec.id for s in sections):
                    # Ids key the build report and notes; never let a mod section shadow another one.
                    new_id, n = f"{mod.id}/{sec.id}", 2
                    while any(s.id == new_id for s in sections):
                        new_id, n = f"{mod.id}/{sec.id}-{n}", n + 1
                    log(f"  {mod.id}: section id '{sec.id}' is already used; calling it '{new_id}'")
                    sec.id = new_id
                sections.append(sec)
    return sections, skipped
