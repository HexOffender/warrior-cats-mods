"""Format-preserving CSV editing for the game's NonAsset data tables.

Only rows you change are re-serialized; every other byte (quoting, line endings, BOM, a
missing trailing newline) stays exactly as the game shipped it.

Edits use the row key (first column) and the column name (matched without regard to case):
    {"Mice": {"BaseExperience": 50}}          set one cell
    {"Gameplay.X.Y": 2}                       key/value tables: sets the first value column
    {"*": {"BaseExperience": "x2"}}           every row; "x2" multiplies the number in the cell
    {"-": ["53"]}                             remove rows by key ("-": "53" is one row too)
    {"+": [{"#": "91", "Preffix": "Moth"}]}   add rows at the end (missing columns stay empty)
Values are numbers, text, true/false (TRUE/FALSE) or "xN". Inside one set of edits the order is fixed,
whatever order the keys come in: removals, then "*" on every row, then the named rows, then additions. A
named row's plain value replaces what "*" made of that cell; its own "xN" multiplies the cell as it was
before this set's "*", so the two never compound. Between sets (two mods) each applies to the text the
one before left, so two mods' "x2" make x4.

A number is written with at most six decimals. A cell that holds a number keeps it when the new value
isn't one ('abc', '1,5'): that is a problem, not a change.
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


def is_number(text):
    """True for a cell or a value that reads as a plain number ("25", " -1.5 "); not "1,5", "1e3" or ""."""
    return isinstance(text, str) and bool(_NUM.match(text.strip()))


def multiplier(value):
    """N for an "xN" (or "*N") value, else None."""
    m = _MULT.match(value) if isinstance(value, str) else None
    return float(m.group(1)) if m else None


def _number(v, original):
    """A number in the style of the original cell: whole when it is whole and the cell had no decimals,
    else with at most six decimals."""
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError(f"{v} isn't a number the game can read")
    if v.is_integer() and "." not in original:
        return str(int(v))
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def format_value(original, value):
    """Render a new cell value in the style of the original cell. A ValueError says why a value can't go in:
    a multiplier on a cell that isn't a number, or text into a cell that holds a number (which keeps its
    number)."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        n = multiplier(value)
        if n is not None:
            if not is_number(original):
                raise ValueError(f"can't multiply '{original}' (not a number)" if original.strip()
                                 else "can't multiply an empty cell")
            return _number(float(original) * n, original)
        if is_number(original) and not is_number(value):
            raise ValueError(f"'{value}' isn't a number; kept {original.strip()}")
        return value.strip() if is_number(value) else value
    if isinstance(value, (int, float)):
        return _number(value, original)
    raise ValueError(f"{value!r} isn't a value a table can hold (use a number, text, true or false)")


def _row_names(spec):
    """The rows a "-" removes: a list of row names, or one name as a string. None for anything else."""
    if isinstance(spec, (str, int)) and not isinstance(spec, bool):
        return [str(spec)]
    if isinstance(spec, list) and all(isinstance(k, (str, int)) and not isinstance(k, bool) for k in spec):
        return [str(k) for k in spec]
    return None


def apply_edits(text, edits, how=None):
    """Apply {row: value | {column: value}} edits in the fixed order (the module's docstring). Returns
    (new_text, applied, problems): applied is [(row, column, from, to)], one per cell changed (its first
    value and its last, so "*" then a row's own value is one change), problems are sentences; a mistake in
    one edit never stops the others. `how`, a dict when given, gets {(row, column): True} for a cell whose
    last change was an "xN" multiplier, False for one set to a plain value. A key or column starting with
    "_" is a note, not an edit."""
    table = Table(text)
    applied, problems = [], []
    cells = {}   # (row, column) -> [row key, column name, first value, last value]
    if not isinstance(edits, dict):
        return table.to_text(), applied, ["the edits for a table should be an object of rows"]
    # 1. Removals.
    if "-" in edits:
        names = _row_names(edits["-"])
        if names is None:
            problems.append('"-" should be a list of the row names to remove')
            names = []
        for key in names:
            rows = table.find_rows(key) if key != "*" else []
            if not rows:
                problems.append(f"no row '{key}' to remove")
            for r in rows:
                table.remove(r)
                applied.append((key, "(row)", "present", "removed"))

    def columns(key, spec):
        if isinstance(spec, dict):
            return {c: v for c, v in spec.items() if not str(c).startswith("_")}
        if len(table.header) < 2:
            problems.append(f"{key}: this table has only its key column, so a value needs a column's name")
            return {}
        return {table.header[1]: spec}

    def change(r, col, value, key, col_name, original=None):
        old = r.fields[col] if col < len(r.fields) else ""
        try:
            new = format_value(old if original is None else original, value)
        except ValueError as e:
            problems.append(f"{key}.{col_name}: {e}")
            return
        if new != old:
            table.set(r, col, new)
            cells.setdefault((id(r), col), [r.fields[0], table.header[col], old, None])[3] = new
            if how is not None:
                how[(r.fields[0], table.header[col])] = multiplier(value) is not None

    def column(col_name):
        try:
            col = table.column(col_name)
        except KeyError as e:
            problems.append(e.args[0])
            return None
        if col == 0:
            problems.append(f"'{col_name}' is the row key and can't be changed")
            return None
        return col

    keys = [k for k in edits if not str(k).startswith("_") and k not in ("+", "-")]
    # 2. "*" on every row, keeping what each cell held before it, for a named row's own "xN".
    before, star_cols = {}, {}
    if "*" in edits:
        for col_name, value in columns("*", edits["*"]).items():
            col = column(col_name)
            if col is None:
                continue
            star_cols[col] = value
            skipped = 0
            for r in table.rows:
                old = before[(id(r), col)] = r.fields[col] if col < len(r.fields) else ""
                if multiplier(value) is not None and not is_number(old):
                    skipped += 1   # an empty or text cell: nothing to multiply, said once for the column below
                    continue
                change(r, col, value, "*", col_name)
            if skipped:
                problems.append(f"*.{table.header[col]}: {skipped} row{'s' if skipped != 1 else ''} with no number "
                                "there, left as they are")
    # 3. The named rows, over what "*" made.
    star_at = keys.index("*") if "*" in keys else None
    for i, key in enumerate(keys):
        if key == "*":
            continue
        rows = table.find_rows(str(key))
        if not rows:
            problems.append(f"no row '{key}'")
            continue
        for col_name, value in columns(key, edits[key]).items():
            col = column(col_name)
            if col is None:
                continue
            for r in rows:
                was = before.get((id(r), col))
                own = multiplier(value) is not None
                if was is not None:
                    # Until this version the keys' order decided: a row before "*" was multiplied by it, and a
                    # row's own "xN" after it multiplied its result. Said for a release where the result moved.
                    try:
                        now = format_value(was, value)
                        then = (format_value(now, star_cols[col]) if i < star_at
                                else format_value(r.fields[col] if col < len(r.fields) else "", value))
                        if then != now and own:
                            problems.append(f'{key}.{table.header[col]}: this file\'s own "{value}" now multiplies '
                                            f'the value from before its "*" ({now}, not {then})')
                        elif then != now:
                            problems.append(f"{key}.{table.header[col]}: this file's own value now wins over its "
                                            f'"*" ({now}, not {then}); the Game data page always showed {now}')
                    except ValueError:
                        pass
                change(r, col, value, key, col_name, original=was if own and was is not None else None)
    applied += [tuple(c) for c in cells.values() if c[2] != c[3]]
    # 4. Additions.
    if "+" in edits:
        adds = edits["+"]
        if not isinstance(adds, list) or not all(isinstance(row, dict) for row in adds):
            problems.append('"+" should be a list of rows to add, each an object of column: value')
            adds = []
        for row in adds:
            row = {c: v for c, v in row.items() if not str(c).startswith("_")}   # a "_note" is a note
            key = ""
            for col_name, value in row.items():
                try:
                    if table.column(col_name) == 0:
                        key = str(value)
                except KeyError:
                    pass
            if not key or table.find_rows(key):
                problems.append(f"can't add row '{key}': " + ("it needs a key" if not key else "it already exists"))
                continue
            fields = [""] * len(table.header)
            try:
                for col_name, value in row.items():
                    fields[table.column(col_name)] = format_value("", value)
            except KeyError as e:
                problems.append(f"can't add row '{key}': {e.args[0]}")
                continue
            except ValueError as e:
                problems.append(f"can't add row '{key}': {e}")
                continue
            table.append(fields)
            applied.append((key, "(row)", "", "added"))
    return table.to_text(), applied, problems
