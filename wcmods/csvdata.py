"""Format-preserving CSV editing for the game's NonAsset data tables.

Only rows you change are re-serialized; every other byte (quoting, line endings, BOM, a
missing trailing newline) stays exactly as the game shipped it.

Edits use the row key (first column) and the column name:
    {"Mice": {"BaseExperience": 50}}          set one cell
    {"Gameplay.X.Y": 2}                       key/value tables: sets the first value column
    {"*": {"BaseExperience": "x2"}}           every row; "x2" multiplies the original number
    {"-": ["53"]}                             remove rows by key
    {"+": [{"#": "91", "Preffix": "Moth"}]}   add rows at the end (missing columns stay empty)
Removals run first, then cell edits, then additions.
"""
import re


class Record:
    __slots__ = ("fields", "quoted", "raw", "sep", "dirty")

    def __init__(self, fields, quoted, raw, sep):
        self.fields, self.quoted, self.raw, self.sep, self.dirty = fields, quoted, raw, sep, False


class Table:
    def __init__(self, text):
        self.prefix = "﻿" if text.startswith("﻿") else ""
        body = text[len(self.prefix):]
        self.records = _parse(body)
        if not self.records:
            raise ValueError("empty CSV")
        self.header = self.records[0].fields

    @property
    def rows(self):
        return self.records[1:]

    def column(self, name):
        for i, h in enumerate(self.header):
            if h == name:
                return i
        low = str(name).lower()
        for i, h in enumerate(self.header):
            if h.lower() == low:
                return i
        raise KeyError(f"no column '{name}' (columns: {', '.join(self.header[1:])})")

    def find_rows(self, key):
        if key == "*":
            return self.rows
        return [r for r in self.rows if r.fields and r.fields[0] == key]

    def set(self, rec, col, value):
        while len(rec.fields) <= col:
            rec.fields.append("")
            rec.quoted.append(False)
        rec.fields[col] = value
        rec.dirty = True

    def append(self, fields):
        """Add a row at the end in the file's own line ending (and keep a missing final newline missing)."""
        fields = list(fields) + [""] * (len(self.header) - len(fields))
        last = self.records[-1]
        rec = Record(fields, [False] * len(fields), "", last.sep)
        rec.dirty = True
        last.sep = self.records[0].sep or "\n"
        self.records.append(rec)
        return rec

    def remove(self, rec):
        i = self.records.index(rec)
        if i == len(self.records) - 1:
            self.records[i - 1].sep = rec.sep   # the new last row ends the way the old one did
        del self.records[i]

    def to_text(self):
        out = [self.prefix]
        for r in self.records:
            out.append(_serialize(r) if r.dirty else r.raw)
            out.append(r.sep)
        return "".join(out)

    def as_dict(self):
        return {"header": self.header, "rows": [r.fields for r in self.rows]}


def _parse(text):
    records = []
    i, n = 0, len(text)
    while i < n:
        start = i
        fields, quoted, cur, was_quoted, inq = [], [], [], False, False
        while i < n:
            c = text[i]
            if inq:
                if c == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        cur.append('"')
                        i += 2
                        continue
                    inq = False
                    i += 1
                    continue
                cur.append(c)
                i += 1
                continue
            if c == '"' and not cur:
                inq = was_quoted = True
                i += 1
            elif c == ",":
                fields.append("".join(cur)); quoted.append(was_quoted)
                cur, was_quoted = [], False
                i += 1
            elif c in "\r\n":
                break
            else:
                cur.append(c)
                i += 1
        fields.append("".join(cur)); quoted.append(was_quoted)
        raw = text[start:i]
        if text.startswith("\r\n", i):
            sep = "\r\n"
        elif i < n:
            sep = text[i]
        else:
            sep = ""
        i += len(sep)
        records.append(Record(fields, quoted, raw, sep))
    return records


def _serialize(rec):
    parts = []
    for value, q in zip(rec.fields, rec.quoted):
        if q or any(ch in value for ch in ',"\r\n'):
            parts.append('"' + value.replace('"', '""') + '"')
        else:
            parts.append(value)
    return ",".join(parts)


_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_MULT = re.compile(r"^\s*[x*]\s*(-?\d+(\.\d+)?)\s*$", re.I)


def format_value(original, value):
    """Render a new cell value in the style of the original cell."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        m = _MULT.match(value)
        if m:
            if not _NUM.match(original.strip()):
                raise ValueError(f"can't multiply '{original}' (not a number)")
            value = float(original) * float(m.group(1))
        else:
            return value
    if isinstance(value, (int, float)):
        v = float(value)
        if v.is_integer() and "." not in original:
            return str(int(v))
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    raise ValueError(f"unsupported value {value!r}")


def apply_edits(text, edits):
    """Apply {row: value | {column: value}} edits. Returns (new_text, applied, problems)."""
    table = Table(text)
    applied, problems = [], []
    for key in edits.get("-", []):
        rows = table.find_rows(str(key)) if key != "*" else []
        if not rows:
            problems.append(f"no row '{key}' to remove")
        for r in rows:
            table.remove(r)
            applied.append((str(key), "(row)", "present", "removed"))
    for key, spec in edits.items():
        if str(key).startswith("_") or key in ("+", "-"):
            continue
        rows = table.find_rows(str(key))
        if not rows:
            problems.append(f"no row '{key}'")
            continue
        cols = spec if isinstance(spec, dict) else {table.header[1]: spec}
        for col_name, value in cols.items():
            try:
                col = table.column(col_name)
            except KeyError as e:
                problems.append(str(e))
                continue
            if col == 0:
                problems.append(f"'{col_name}' is the row key and can't be changed")
                continue
            for r in rows:
                old = r.fields[col] if col < len(r.fields) else ""
                try:
                    new = format_value(old, value)
                except ValueError as e:
                    problems.append(f"{key}.{col_name}: {e}")
                    continue
                if new != old:
                    table.set(r, col, new)
                    applied.append((r.fields[0], table.header[col], old, new))
    for row in edits.get("+", []):
        key = str(row.get(table.header[0], ""))
        if not key or table.find_rows(key):
            problems.append(f"can't add row '{key}': " + ("it needs a key" if not key else "it already exists"))
            continue
        fields = [""] * len(table.header)
        try:
            for col_name, value in row.items():
                fields[table.column(col_name)] = format_value("", value)
        except (KeyError, ValueError) as e:
            problems.append(f"can't add row '{key}': {e}")
            continue
        table.append(fields)
        applied.append((key, "(row)", "", "added"))
    return table.to_text(), applied, problems
