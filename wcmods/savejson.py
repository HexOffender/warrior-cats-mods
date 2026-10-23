"""Format-preserving edits to the save's JSON text.

Paths are '/'-separated and start inside the save's account object, e.g.
    Shared/SettingsData/Minimap
    0/GameplayProgression/Experience
    0/GameplayProgression/State/Inventory/Gameplay.Inventory.Consumable.SmallCatnip
Keys may contain dots (the game's tags do), so dots are never separators.
Only the edited value's characters change; indentation and number formatting elsewhere stay.
"""
import json


def split(path):
    return tuple(p for p in str(path).strip("/").split("/") if p != "")


def _spans(text):
    spans = {}
    n = len(text)

    def ws(i):
        while i < n and text[i] in " \t\r\n":
            i += 1
        return i

    def string(i):
        j = i + 1
        while text[j] != '"':
            j += 2 if text[j] == "\\" else 1
        return json.loads(text[i:j + 1]), j + 1

    def value(i, path):
        i = ws(i)
        c = text[i]
        if c == "{":
            start, i = i, ws(i + 1)
            if text[i] != "}":
                while True:
                    key, i = string(ws(i))
                    i = ws(i)
                    i = value(i + 1, path + (key,))
                    i = ws(i)
                    if text[i] == ",":
                        i += 1
                        continue
                    break
            spans[path] = (start, i + 1, "object")
            return i + 1
        if c == "[":
            start, i, k = i, ws(i + 1), 0
            if text[i] != "]":
                while True:
                    i = value(i, path + (str(k),))
                    k += 1
                    i = ws(i)
                    if text[i] == ",":
                        i += 1
                        continue
                    break
            spans[path] = (start, i + 1, "array")
            return i + 1
        if c == '"':
            _, j = string(i)
            spans[path] = (i, j, "string")
            return j
        j = i
        while j < n and text[j] not in ",}] \t\r\n":
            j += 1
        spans[path] = (i, j, "number" if text[i] not in "tfn" else "literal")
        return j

    value(0, ())
    return spans


class SaveDoc:
    def __init__(self, text):
        self.text = text
        doc = json.loads(text)
        if len(doc) != 1:
            raise ValueError("unexpected save layout")
        self.account = next(iter(doc))
        self.data = doc[self.account]

    def _full(self, path):
        return (self.account,) + split(path)

    def get(self, path):
        node = self.data
        for part in split(path):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    def exists(self, path):
        try:
            self.get(path)
            return True
        except (KeyError, IndexError, ValueError, TypeError):
            return False

    def set(self, path, value):
        """Replace an existing value. Containers are replaced wholesale with compact JSON."""
        spans = _spans(self.text)
        key = self._full(path)
        if key not in spans:
            raise KeyError(f"no value at {path}")
        start, end, _ = spans[key]
        self.text = self.text[:start] + _dump(value) + self.text[end:]
        self.__init__(self.text)

    def insert(self, object_path, key, value):
        """Add a key to an existing object (used for new inventory items and similar)."""
        spans = _spans(self.text)
        full = self._full(object_path)
        if full not in spans or spans[full][2] != "object":
            raise KeyError(f"{object_path} is not an object in the save")
        if self.exists(f"{object_path}/{key}"):
            return self.set(f"{object_path}/{key}", value)
        start, end, _ = spans[full]
        nl = "\r\n" if "\r\n" in self.text else "\n"
        line_start = self.text.rfind("\n", 0, start) + 1
        indent = ""
        while self.text[line_start + len(indent)] in " \t":
            indent += self.text[line_start + len(indent)]
        child = indent + "\t"
        entry = f"{json.dumps(key)}: {_dump(value)}"
        inner = self.text[start + 1:end - 1]
        if inner.strip():
            new = self.text[:start + 1] + nl + child + entry + "," + inner + self.text[end - 1:]
        else:
            new = self.text[:start + 1] + nl + child + entry + nl + indent + self.text[end - 1:]
        self.__init__(new)


def _dump(value):
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, float):
        return repr(value)
    return json.dumps(value, ensure_ascii=False)
