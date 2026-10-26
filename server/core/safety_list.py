"""Local phrase list for requests Astra will not answer.

Feelings are not methods. "I feel like hurting myself" stays open.
"How do I hurt myself" is a method request and is blocked.
The matched phrase is never copied into the spoken refusal.
"""

from __future__ import annotations

import re
import unicodedata

REFUSAL = "I can't help with that."

# Stable ids stored in notes["safety"]["category"].
VIOLENT_CRIME = "violent_crime"
EXPLOSIVES_WEAPONS = "explosives_weapons"
CHILD_SEXUAL = "child_sexual"
SCAM_THEFT = "scam_theft"
BIO_CHEM = "bio_chem"
SELF_HARM = "self_harm"

# Multi-word requests only. Longer phrases are tried first.
_PHRASES: tuple[tuple[str, str], ...] = (
    ("how to make a pipe bomb", EXPLOSIVES_WEAPONS),
    ("how to build a pipe bomb", EXPLOSIVES_WEAPONS),
    ("how to synthesize a nerve agent", BIO_CHEM),
    ("sexual abuse of a child", CHILD_SEXUAL),
    ("sexual images of children", CHILD_SEXUAL),
    ("how to steal credit cards", SCAM_THEFT),
    ("how to steal a password", SCAM_THEFT),
    ("how to steal passwords", SCAM_THEFT),
    ("how to hack a password", SCAM_THEFT),
    ("how to make explosives", EXPLOSIVES_WEAPONS),
    ("how to make a bioweapon", BIO_CHEM),
    ("how to commit suicide", SELF_HARM),
    ("how do i kill myself", SELF_HARM),
    ("how to kill myself", SELF_HARM),
    ("ways to kill myself", SELF_HARM),
    ("how to cut my wrists", SELF_HARM),
    ("how do i hurt myself", SELF_HARM),
    ("how to hurt myself", SELF_HARM),
    ("how to shoot someone", VIOLENT_CRIME),
    ("how to kill someone", VIOLENT_CRIME),
    ("how to make a bomb", EXPLOSIVES_WEAPONS),
    ("how to build a bomb", EXPLOSIVES_WEAPONS),
    ("how to make napalm", EXPLOSIVES_WEAPONS),
    ("how to build a gun", EXPLOSIVES_WEAPONS),
    ("how to make a gun", EXPLOSIVES_WEAPONS),
    ("how to make sarin", BIO_CHEM),
    ("how to make anthrax", BIO_CHEM),
    ("how to make ricin", BIO_CHEM),
    ("how to make vx", BIO_CHEM),
    ("credential stuffing", SCAM_THEFT),
    ("how to scam people", SCAM_THEFT),
    ("child pornography", CHILD_SEXUAL),
    ("suicide methods", SELF_HARM),
    ("how to overdose", SELF_HARM),
    ("how to kidnap", VIOLENT_CRIME),
    ("how to torture", VIOLENT_CRIME),
    ("how to murder", VIOLENT_CRIME),
    ("how do i kill", VIOLENT_CRIME),
    ("how to phish", SCAM_THEFT),
    ("how to stab", VIOLENT_CRIME),
    ("child porn", CHILD_SEXUAL),
    ("csam", CHILD_SEXUAL),
)

_SORTED = tuple(sorted(_PHRASES, key=lambda item: len(item[0]), reverse=True))
_PATTERNS = tuple(
    (re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)"), category)
    for phrase, category in _SORTED
)


# Marks and format chars are deleted so they cannot split a word into a miss.
_DROP_CATEGORIES = frozenset({"Mn", "Me", "Cf"})

# Letters that look like ASCII. Applied after casefold, so only lowercase.
_CONFUSABLES = str.maketrans(
    {
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u0445": "x",
        "\u0456": "i",
        "\u0455": "s",
        "\u04bb": "h",
        "\u0501": "d",
        "\u0261": "g",
        "\u03bf": "o",
        "\u03b1": "a",
        "\u03b9": "i",
        "\u03b5": "e",
        "\u043a": "k",
        "\u0442": "t",
        "\u043c": "m",
        "\u043d": "h",
        "\u0432": "b",
    }
)
# Digits and symbols people swap into a word. "2" stays a digit so "how 2" can
# still be read as "how to" without turning every 2 into the letter t.
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

_HOW_TO = "howto"
_HOW_ALIASES = ("howdoi", "howcani", "howcouldi", "howshouldi", "how2", "waysto")
_ARTICLE_VERBS = ("make", "build", "steal", "hack", "synthesize")
_ARTICLE_WORDS = ("a", "an", "the", "one")


def normalize_text(text: str) -> str:
    """Casefold and turn punctuation into spaces so phrases match on words."""
    raw = unicodedata.normalize("NFKC", text or "")
    raw = "".join(ch for ch in raw if unicodedata.category(ch) not in _DROP_CATEGORIES)
    folded = raw.casefold().translate(_CONFUSABLES).translate(_LEET)
    folded = folded.replace("_", " ")
    folded = "".join(" " if unicodedata.category(ch) == "Pc" else ch for ch in folded)
    cleaned = re.sub(r"[^\w\s]", " ", folded, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _alias_requests(norm: str) -> str:
    """Map spoken how-to shapes onto the phrase list without dropping the original."""
    # One polite filler must not split "how do I" from the rest of the phrase.
    out = re.sub(
        r"\b((?:how (?:do|can|could|should) i|how to|ways to|how 2)) "
        r"(?:please|just|kindly|actually)\b",
        r"\1",
        norm,
    )
    out = re.sub(r"\bhow (?:do|can|could|should) i\b", "how to", out)
    out = re.sub(r"\bhow 2\b", "how to", out)
    return re.sub(r"\bways to\b", "how to", out)


def _compact(norm: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for index, ch in enumerate(norm):
        if ch.isalnum():
            chars.append(ch)
            positions.append(index)
    return "".join(chars), positions


def _bounded(positions: list[int], start: int, end: int) -> bool:
    """Reject a hit that begins or ends in the middle of a longer word."""
    if start > 0 and positions[start] == positions[start - 1] + 1:
        return False
    if end < len(positions) and positions[end] == positions[end - 1] + 1:
        return False
    return True


def _needle_forms(needle: str) -> list[str]:
    """Plurals and how-do-I / missing-article forms of one compact phrase."""
    forms = [needle + "s"]
    if not needle.startswith(_HOW_TO):
        return forms
    rest = needle[len(_HOW_TO) :]
    for alias in _HOW_ALIASES:
        forms.append(alias + rest)
        forms.append(alias + rest + "s")
    for verb in _ARTICLE_VERBS:
        article = verb + "a"
        if article in needle:
            bare = needle.replace(article, verb, 1)
            forms.append(bare)
            forms.append(bare + "s")
            if bare.startswith(_HOW_TO):
                bare_rest = bare[len(_HOW_TO) :]
                for alias in _HOW_ALIASES:
                    forms.append(alias + bare_rest)
                    forms.append(alias + bare_rest + "s")
        elif verb in needle:
            idx = needle.find(verb)
            inserted = needle[: idx + len(verb)] + "a" + needle[idx + len(verb) :]
            forms.append(inserted)
            forms.append(inserted + "s")
    return forms


def _extra_phrases(phrase: str) -> list[str]:
    """Same request with a different article, or child/children.

    Built from the spaced phrase so the article is a word. Compact "makea"
    would eat the first letter of "anthrax".
    """
    extras: list[str] = []
    words = phrase.split()
    for i, word in enumerate(words):
        if word in _ARTICLE_WORDS:
            for other in _ARTICLE_WORDS:
                if other == word:
                    continue
                swapped = words.copy()
                swapped[i] = other
                extras.append(" ".join(swapped))
            dropped = words[:i] + words[i + 1 :]
            if dropped:
                extras.append(" ".join(dropped))
        if (
            word in _ARTICLE_VERBS
            and i + 1 < len(words)
            and words[i + 1] not in _ARTICLE_WORDS
        ):
            for art in _ARTICLE_WORDS:
                inserted = words[: i + 1] + [art] + words[i + 1 :]
                extras.append(" ".join(inserted))
    if phrase.endswith(" porn"):
        extras.append(phrase + "o")
    if phrase.endswith(" pornography"):
        extras.append(phrase[:-1] + "ic")
    more: list[str] = []
    for item in (phrase, *extras):
        tokens = item.split()
        if "child" in tokens:
            more.append(" ".join("children" if tok == "child" else tok for tok in tokens))
        if "children" in tokens:
            child_tokens = ["child" if tok == "children" else tok for tok in tokens]
            more.append(" ".join(child_tokens))
            idx = child_tokens.index("child")
            if idx == 0 or child_tokens[idx - 1] not in _ARTICLE_WORDS:
                for art in ("a", "the"):
                    inserted = child_tokens[:idx] + [art] + child_tokens[idx:]
                    more.append(" ".join(inserted))
    extras.extend(more)
    return extras


def _phrase_forms(phrase: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in (phrase, *_extra_phrases(phrase)):
        base = re.sub(r"[^a-z0-9]", "", item)
        for form in (base, *_needle_forms(base)):
            if len(form) < 4 or form in seen:
                continue
            seen.add(form)
            out.append(form)
    return out


_SEEN_NEEDLES: set[str] = set()
_RAW_NEEDLES: list[tuple[str, str]] = []
for _phrase, _category in _SORTED:
    for _needle in _phrase_forms(_phrase):
        if _needle in _SEEN_NEEDLES:
            continue
        _SEEN_NEEDLES.add(_needle)
        _RAW_NEEDLES.append((_needle, _category))
# Longer needles first so "bombastic" cannot lose to a shorter "bomb" form.
_COMPACT = tuple(sorted(_RAW_NEEDLES, key=lambda item: len(item[0]), reverse=True))


def _compact_hit(compact: str, positions: list[int], needle: str) -> bool:
    if len(needle) < 4 or not compact:
        return False
    start = 0
    while start < len(compact):
        found = compact.find(needle, start)
        if found < 0:
            return False
        if _bounded(positions, found, found + len(needle)):
            return True
        start = found + 1
    return False


def _match_norm(norm: str) -> str | None:
    for pattern, category in _PATTERNS:
        if pattern.search(norm):
            return category
    compact, positions = _compact(norm)
    if not compact:
        return None
    for needle, category in _COMPACT:
        if _compact_hit(compact, positions, needle):
            return category
    return None


def match_category(text: str) -> str | None:
    """Return a category id when a blocked phrase matches, else None."""
    norm = normalize_text(text)
    if not norm:
        return None
    hit = _match_norm(norm)
    if hit:
        return hit
    aliased = _alias_requests(norm)
    if aliased == norm:
        return None
    return _match_norm(aliased)
