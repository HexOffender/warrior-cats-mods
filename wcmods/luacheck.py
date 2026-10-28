"""A light structure check for the Lua scripts wcmods generates and the ones mods bring: balanced blocks
and brackets.

There's no Lua on the machine to parse them, and a missing `end` would only show up in game, as a
load error in UE4SS.log. This tokenises Lua 5.4 (strings, long strings, comments) and checks that
every function/if/do/repeat block and every bracket is closed in order. It doesn't check expressions.
check() gives the problems as short notes for the build's log; explain() says one in a creator's words.
"""
import re

_TOKEN = re.compile(r"""
    (?P<long>\[(?P<eq>=*)\[)                  # long string or, after --, long comment
  | (?P<comment>--)
  | (?P<string>"(?:\\(?:\r\n|[\s\S])|[^"\\\n])*"|'(?:\\(?:\r\n|[\s\S])|[^'\\\n])*')   # a \ before a line end continues it
  | (?P<number>0[xX][0-9a-fA-F.]+(?:[pP][+-]?\d+)?|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_]\w*)
  | (?P<symbol>\.\.\.|\.\.|==|~=|<=|>=|<<|>>|//|::|[-+*/%^#&~|<>=(){}\[\];:,.])
  | (?P<space>\s+)
  | (?P<bad>.)
""", re.VERBOSE)

_OPENS = {"function": "end", "if": "end", "do": "end", "repeat": "until", "(": ")", "[": "]", "{": "}"}
_CLOSERS = {"end", "until", ")", "]", "}"}


def check(source):
    """Return a list of problems ("line 12: 'end' closes 'repeat' from line 3"); empty if it looks balanced."""
    problems, stack = [], []
    pos, line = 0, 1
    while pos < len(source):
        m = _TOKEN.match(source, pos)
        kind, text = m.lastgroup, m.group()
        start_line = line
        if kind == "comment":
            long = re.compile(r"\[(=*)\[").match(source, m.end())
            if long:
                end = source.find("]" + long.group(1) + "]", long.end())
                if end < 0:
                    problems.append(f"line {line}: long comment never closed")
                    return problems
                text = source[pos:end + len(long.group(1)) + 2]
            else:
                nl = source.find("\n", pos)
                text = source[pos:] if nl < 0 else source[pos:nl]
        elif kind == "long":
            end = source.find("]" + m.group("eq") + "]", m.end())
            if end < 0:
                problems.append(f"line {line}: long string never closed")
                return problems
            text = source[pos:end + len(m.group("eq")) + 2]
        elif kind == "bad":
            if text in "\"'":
                problems.append(f"line {line}: string never closed")
            else:
                problems.append(f"line {line}: unexpected character {text!r}")
        elif kind in ("name", "symbol"):
            if text in _OPENS:
                stack.append((text, line))
            elif text in _CLOSERS:
                if not stack:
                    problems.append(f"line {line}: '{text}' with nothing open")
                else:
                    opened, at = stack.pop()
                    if _OPENS[opened] != text:
                        problems.append(f"line {line}: '{text}' closes '{opened}' from line {at}")
        line = start_line + text.count("\n")
        pos += len(text)
    for opened, at in reversed(stack):   # the innermost first: the likeliest to be the one missing its end
        problems.append(f"line {at}: '{opened}' is never closed")
    return problems


_NEVER_CLOSED = re.compile(r"^line (\d+): '([^']+)' is never closed$")
_CLOSES = re.compile(r"^line (\d+): '([^']+)' closes '([^']+)' from line (\d+)$")
_NOTHING_OPEN = re.compile(r"^line (\d+): '([^']+)' with nothing open$")
_PLAIN = {"string never closed": "a piece of text in quotes is never closed (its closing quote is missing)",
          "long string never closed": "a [[ long text ]] is never closed with ]]",
          "long comment never closed": "a --[[ comment ]] is never closed with ]]"}


def explain(problem):
    """One of check()'s problems in a creator's words: "line 4: a "function" is never closed with "end""."""
    m = _NEVER_CLOSED.match(problem)
    if m:
        line, opened = m.groups()
        return f'line {line}: a "{opened}" is never closed with "{_OPENS[opened]}"'
    m = _CLOSES.match(problem)
    if m:
        line, closer, opened, at = m.groups()
        return f'line {line}: this "{closer}" is where the "{opened}" from line {at} should be closed with "{_OPENS[opened]}"'
    m = _NOTHING_OPEN.match(problem)
    if m:
        line, closer = m.groups()
        return f'line {line}: an "{closer}" with nothing before it to close (one too many, or its start is missing)'
    line, _, rest = problem.partition(": ")
    if rest in _PLAIN:
        return f"{line}: {_PLAIN[rest]}"
    m = re.match(r"^unexpected character (.+)$", rest)
    if m:
        return f"{line}: a character Lua doesn't use, {m.group(1)} (copied from a word processor?)"
    return problem
