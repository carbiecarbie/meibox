"""'Como a Mei te chama': editing the player's name with arcade-style letters (design 12.4 of the copilot).

Up/down change the letter, left/right move between positions, A saves, B erases (or goes back when empty).
Only capitals while editing (A-Z, space and the Portuguese accented letters); up to 12 letters.
Saved with only the first letter in capitals ("LULU" -> "Lulu"). Empty = Mei uses no name.
The copilot reads it from settings["player_name"].
"""

ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("ÁÀÂÃÉÊÍÓÔÕÚÇ") + [" "]
MAX_LEN = 12


def to_saved(letters):
    """Edited letters -> stored name: single spaces, trimmed, only the first letter in capitals."""
    s = " ".join("".join(letters).split())[:MAX_LEN].strip()
    return s[:1].upper() + s[1:].lower()


def to_editable(name):
    """Stored name -> capital letters the editor knows (anything else is dropped)."""
    return [ch for ch in (name or "").upper() if ch in ALPHABET][:MAX_LEN]


class NameEditor:
    def __init__(self, name=""):
        self.letters = to_editable(name)
        self.pos = min(len(self.letters), MAX_LEN - 1)   # starts on the empty slot after the name

    def current(self):
        return self.letters[self.pos] if self.pos < len(self.letters) else None

    def change(self, step):
        """step +1 = next letter (up), -1 = previous (down). An empty slot starts at A (or Z going down)."""
        cur = self.current()
        if cur is None:
            new = "A" if step > 0 else "Z"
            self.letters.append(new)
        else:
            i = ALPHABET.index(cur)
            self.letters[self.pos] = ALPHABET[(i + step) % len(ALPHABET)]

    def move(self, step):
        """Left/right. The cursor can stand on one empty slot after the name, never past 12."""
        last = min(len(self.letters), MAX_LEN - 1)
        self.pos = max(0, min(last, self.pos + step))

    def erase(self):
        """B: removes the letter under the cursor (or the last one, on the empty slot).
        Returns False when there was nothing to erase (the screen then goes back)."""
        if not self.letters:
            return False
        if self.pos < len(self.letters):
            del self.letters[self.pos]
        else:
            self.letters.pop()
        self.pos = min(self.pos, len(self.letters), MAX_LEN - 1)
        return True

    def saved(self):
        return to_saved(self.letters)
