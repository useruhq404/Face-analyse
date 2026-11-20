"""Boîte à outils crypto / encodage — hors ligne, déterministe.

Hachage, identification de hash, encodeurs réversibles (base64, URL, hex, ROT13,
binaire, morse), générateur de mot de passe et estimation d'entropie. Aucun
réseau. Rien ici ne « casse » un hash : pas de bruteforce, pas de dictionnaire.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import re
import secrets
import string
from urllib.parse import quote, unquote

HASH_ALGOS = ("md5", "sha1", "sha256", "sha512")


def hash_text(algo: str, text: str) -> str:
    algo = algo.lower()
    if algo not in hashlib.algorithms_available:
        raise ValueError(f"algorithme inconnu : {algo}")
    return hashlib.new(algo, text.encode("utf-8")).hexdigest()


def all_hashes(text: str) -> dict[str, str]:
    return {a: hash_text(a, text) for a in HASH_ALGOS}


#: (nom, longueur hex) → candidats par longueur.
_HASH_BY_LEN = {32: ["MD5", "MD4", "NTLM"], 40: ["SHA-1", "RIPEMD-160"],
                56: ["SHA-224"], 64: ["SHA-256", "SHA3-256", "BLAKE2s"],
                96: ["SHA-384"], 128: ["SHA-512", "SHA3-512", "BLAKE2b"]}


def identify_hash(value: str) -> list[str]:
    """Devine le type d'un hash d'après sa longueur/forme (indicatif, non garanti)."""
    v = value.strip()
    if re.fullmatch(r"\$2[aby]\$\d{2}\$.{53}", v):
        return ["bcrypt"]
    if re.fullmatch(r"\$argon2(id|i|d)\$.+", v):
        return ["Argon2"]
    if v.startswith("$6$"):
        return ["sha512crypt (crypt)"]
    if v.startswith("$1$"):
        return ["md5crypt (crypt)"]
    if not re.fullmatch(r"[0-9a-fA-F]+", v):
        return []
    return _HASH_BY_LEN.get(len(v), [])


# ---------------------------------------------------------------- encodeurs

def b64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64_decode(text: str) -> str:
    pad = "=" * (-len(text.strip()) % 4)
    return base64.b64decode(text.strip() + pad).decode("utf-8", "replace")


def url_encode(text: str) -> str:
    return quote(text, safe="")


def url_decode(text: str) -> str:
    return unquote(text)


def hex_encode(text: str) -> str:
    return text.encode("utf-8").hex()


def hex_decode(text: str) -> str:
    return bytes.fromhex(re.sub(r"\s+", "", text)).decode("utf-8", "replace")


def rot13(text: str) -> str:
    return text.translate(str.maketrans(
        string.ascii_lowercase + string.ascii_uppercase,
        string.ascii_lowercase[13:] + string.ascii_lowercase[:13]
        + string.ascii_uppercase[13:] + string.ascii_uppercase[:13]))


def to_binary(text: str) -> str:
    return " ".join(f"{b:08b}" for b in text.encode("utf-8"))


def from_binary(text: str) -> str:
    bits = re.sub(r"[^01]", "", text)
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits) - len(bits) % 8, 8))
    return data.decode("utf-8", "replace")


_MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.",
    "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.",
    "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-",
    "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....",
    "6": "-....", "7": "--...", "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--",
    "?": "..--..", "/": "-..-.", "@": ".--.-.", "-": "-....-", " ": "/",
}
_MORSE_INV = {v: k for k, v in _MORSE.items()}


def to_morse(text: str) -> str:
    return " ".join(_MORSE.get(c.upper(), "") for c in text).strip()


def from_morse(text: str) -> str:
    return "".join(_MORSE_INV.get(tok, "") if tok != "/" else " " for tok in text.split()).strip()


# ------------------------------------------------------------- mots de passe

def generate_password(length: int = 20, *, symbols: bool = True) -> str:
    length = max(6, min(length, 256))
    alphabet = string.ascii_letters + string.digits + ("!@#$%^&*()-_=+[]{}" if symbols else "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def password_entropy_bits(password: str) -> float:
    pool = 0
    if any(c.islower() for c in password):
        pool += 26
    if any(c.isupper() for c in password):
        pool += 26
    if any(c.isdigit() for c in password):
        pool += 10
    if any(not c.isalnum() for c in password):
        pool += 32
    return round(len(password) * math.log2(pool), 1) if pool else 0.0


def password_strength(password: str) -> str:
    bits = password_entropy_bits(password)
    if bits < 40:
        return f"faible ({bits} bits)"
    if bits < 60:
        return f"moyen ({bits} bits)"
    if bits < 80:
        return f"bon ({bits} bits)"
    return f"fort ({bits} bits)"
