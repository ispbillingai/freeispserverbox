"""Minimal S-expression reader/writer for KiCad files.

KiCad board and footprint files are S-expressions with quoted strings that may
contain escapes. This keeps the tree as nested lists of str tokens so the
generator can splice in placement and net data without regex surgery.
"""


def parse(text):
    """Parse one S-expression from text; returns nested lists."""
    pos = 0
    n = len(text)

    def skip_ws():
        nonlocal pos
        while pos < n and text[pos] in " \t\r\n":
            pos += 1

    def read_atom():
        nonlocal pos
        start = pos
        while pos < n and text[pos] not in " \t\r\n()":
            pos += 1
        return text[start:pos]

    def read_string():
        nonlocal pos
        pos += 1  # opening quote
        out = []
        while pos < n:
            c = text[pos]
            if c == "\\":
                out.append(text[pos:pos + 2])
                pos += 2
                continue
            if c == '"':
                pos += 1
                break
            out.append(c)
            pos += 1
        return '"' + "".join(out) + '"'

    def read_list():
        nonlocal pos
        pos += 1  # opening paren
        items = []
        while True:
            skip_ws()
            if pos >= n:
                raise ValueError("unterminated list")
            c = text[pos]
            if c == ")":
                pos += 1
                return items
            if c == "(":
                items.append(read_list())
            elif c == '"':
                items.append(read_string())
            else:
                items.append(read_atom())

    skip_ws()
    return read_list()


def dumps(node, indent=0):
    """Serialise back to KiCad's tab-indented style."""
    pad = "\t" * indent
    if isinstance(node, str):
        return pad + node
    if not node:
        return pad + "()"

    head = node[0]
    # keep simple all-atom lists on one line, as KiCad does
    if all(isinstance(c, str) for c in node):
        return pad + "(" + " ".join(node) + ")"

    parts = [pad + "(" + (head if isinstance(head, str) else "")]
    rest = node[1:] if isinstance(head, str) else node
    inline = []
    body = []
    for child in rest:
        if isinstance(child, str) and not body:
            inline.append(child)
        else:
            body.append(child)
    if inline:
        parts[0] += " " + " ".join(inline)
    for child in body:
        parts.append(dumps(child, indent + 1))
    parts.append(pad + ")")
    return "\n".join(parts)


def find(node, key):
    """First direct child list whose head is key."""
    for child in node:
        if isinstance(child, list) and child and child[0] == key:
            return child
    return None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def q(s):
    """Quote a value for KiCad output."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def unq(s):
    if isinstance(s, str) and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s
