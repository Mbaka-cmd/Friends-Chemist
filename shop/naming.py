import re

# Words that should stay in capitals on the public site.
KEEP = {"PCM", "ORS", "DM", "BP", "IFAS", "LF", "ABZ", "DCP", "HCL", "CKL"}
EXPAND = {"syp": "Syrup", "susp": "Suspension", "tabs": "Tablets", "tab": "Tablet", "inj": "Injection",
          "exp": "Expectorant", "caps": "Capsules", "pess": "Pessaries", "oint": "Ointment", "gen": "Generic"}
# Names that were cut off in the stock export and cannot be fixed by rules.
OVERRIDES = {"moms magic 100ml (gripe": "Moms Magic Gripe Water 100 ml"}


def _shouting(s):
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.8


def _cap(m):
    w = m.group(0)
    if not w.isupper():
        return w
    if w in KEEP:
        return w
    return EXPAND.get(w.lower(), w.capitalize())


def _brackets(s):
    s = re.sub(r"[\s(\-/,.]+$", "", s)
    if s.count("(") > s.count(")"):
        s += ")"
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    return re.sub(r"\s+", " ", s).strip()


def tidy(name):
    """Turn a stock-list name into something readable for customers."""
    s = re.sub(r"\s+", " ", (name or "")).strip()
    if not s:
        return s
    if s.lower() in OVERRIDES:
        return OVERRIDES[s.lower()]
    if _shouting(s):
        s = re.sub(r"(?<=\w)\(", " (", s)
        s = re.sub(r"\)(?=\w)", ") ", s)
        s = re.sub(r"\b(\d) (\d)(?=\s?(?:ml|mg)\b)", r"\1.\2", s, flags=re.I)
        s = re.sub(r"(\d+)\s*[`'\u2019]\s*S\b", r"\1s", s)
        s = re.sub(r"(\d+)S\b", r"\1s", s)
        s = re.sub(r"(\d+(?:\.\d+)?)\s*MLS?\b", r"\1 ml", s, flags=re.I)
        s = re.sub(r"(\d+(?:\.\d+)?)\s*(?:GMS|GM|G)\b", r"\1 g", s)
        s = re.sub(r"(\d+(?:\.\d+)?)\s*MG\b", r"\1 mg", s)
        s = re.sub(r"(\d+(?:\.\d+)?)\s*KG\b", r"\1 kg", s)
        s = re.sub(r"[A-Za-z][A-Za-z'\u2019]*", _cap, s)
    return _brackets(s)