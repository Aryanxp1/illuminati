import re


def locate(answer: str, text: str, used: set[int]) -> tuple[int, int] | None:
    """Offsets of `text` in `answer`: exact match first, then whitespace-normalised.

    `used` holds start offsets already taken, so repeated text maps to its next occurrence.
    """
    start = answer.find(text)
    while start != -1:
        if start not in used:
            return start, start + len(text)
        start = answer.find(text, start + 1)

    words = text.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    for match in re.finditer(pattern, answer):
        if match.start() not in used:
            return match.start(), match.end()
    return None
