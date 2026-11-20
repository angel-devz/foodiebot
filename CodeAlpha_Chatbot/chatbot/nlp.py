"""Text normalisation shared by training and inference."""
import re

_CONTRACTIONS = {
    "can't": "can not", "won't": "will not", "don't": "do not", "doesn't": "does not",
    "didn't": "did not", "isn't": "is not", "aren't": "are not", "hasn't": "has not",
    "haven't": "have not", "i'm": "i am", "it's": "it is", "what's": "what is",
    "where's": "where is", "that's": "that is", "you're": "you are", "i've": "i have",
    "u": "you", "ur": "your", "pls": "please", "plz": "please", "thx": "thanks",
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def normalize(text: str) -> str:
    """Lower-case, expand contractions/slang and strip punctuation."""
    tokens = _TOKEN_RE.findall(text.lower().replace("’", "'"))
    words = []
    for tok in tokens:
        words.extend(_CONTRACTIONS.get(tok, tok).split())
    return " ".join(w.strip("'") for w in words if w.strip("'"))
