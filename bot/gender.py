from __future__ import annotations

import re
import unicodedata

# Sık görülen Türkçe kadın isimleri (küçük harf, ASCII sadeleştirilmiş + orijinal)
_FEMALE = {
    "ayse",
    "ayşe",
    "fatma",
    "emine",
    "hatice",
    "zeynep",
    "elif",
    "merve",
    "selin",
    "busra",
    "büşra",
    "esra",
    "deniz",  # unisex — kadın varsayımı zayıf; listede tutmuyoruz isteğe bağlı
    "elisa",
    "eliza",
    "ela",
    "ece",
    "eda",
    "eda",
    "gizem",
    "gamze",
    "gul",
    "gül",
    "gulay",
    "gülay",
    "hande",
    "hilal",
    "irem",
    "irem",
    "kübra",
    "kubra",
    "leyla",
    "melike",
    "melisa",
    "melissa",
    "nisa",
    "nur",
    "nurcan",
    "ozge",
    "özge",
    "pelin",
    "pinar",
    "pınar",
    "sena",
    "seda",
    "sevim",
    "sevgi",
    "sibel",
    "tugba",
    "tuğba",
    "yasemin",
    "yagmur",
    "yağmur",
    "zehra",
    "zeliha",
    "asli",
    "aslı",
    "aylin",
    "ayca",
    "ayça",
    "banu",
    "bahar",
    "berna",
    "betul",
    "betül",
    "burcu",
    "canan",
    "cemile",
    "ceren",
    "cigdem",
    "çiğdem",
    "damla",
    "defne",
    "derya",
    "dilara",
    "dilek",
    "ebru",
    "ecrin",
    "elifnaz",
    "emine",
    "esin",
    "fadime",
    "feride",
    "filiz",
    "fulya",
    "fund",
    "gokce",
    "gökçe",
    "gulsah",
    "gülşah",
    "habibe",
    "havva",
    "hayriye",
    "hulya",
    "hülya",
    "ilknur",
    "ilknur",
    "inci",
    "jale",
    "kadriye",
    "kader",
    "lale",
    "latife",
    "melek",
    "meryem",
    "mine",
    "mujgan",
    "müjgan",
    "nazan",
    "nazli",
    "nazlı",
    "nesrin",
    "nevin",
    "nihal",
    "nilufer",
    "nilüfer",
    "nurgul",
    "nurgül",
    "ozlem",
    "özlem",
    "rabia",
    "rukiye",
    "saadet",
    "safiye",
    "sebnem",
    "şebnem",
    "semra",
    "serap",
    "serpil",
    "sevda",
    "sevil",
    "sevilay",
    "songul",
    "songül",
    "sumeyye",
    "sümeyye",
    "sultan",
    "sukran",
    "şükran",
    "tuba",
    "ulku",
    "ülkü",
    "vesile",
    "yalin",
    "yeliz",
    "yesim",
    "yeşim",
    "yildiz",
    "yıldız",
    "zeynep",
    "ziynet",
}

# Açıkça erkek (kadın listesindeki unisex çakışmaları için)
_MALE_FORCE = {
    "umut",
    "umit",
    "ümit",
    "riza",
    "rıza",
    "sergen",
    "mehmet",
    "mustafa",
    "ahmet",
    "ali",
    "hasan",
    "huseyin",
    "hüseyin",
    "ibrahim",
    "ismail",
    "osman",
    "yusuf",
    "emre",
    "can",
    "cem",
    "burak",
    "murat",
    "fatih",
    "kemal",
    "serkan",
    "onur",
    "ozan",
    "tolga",
    "volkan",
    "yasin",
    "yilmaz",
    "denis",
    "dennis",
}


def _fold(text: str) -> str:
    text = text.strip().lower()
    # Türkçe i/ı
    text = text.replace("ı", "i").replace("İ", "i").replace("I", "i")
    # aksanları sadeleştir
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def first_name(full_name: str) -> str:
    parts = re.split(r"[\s._\-]+", (full_name or "").strip())
    return parts[0] if parts else ""


def is_female_name(full_name: str) -> bool:
    fn = first_name(full_name)
    if not fn:
        return False
    folded = _fold(fn)
    if folded in _MALE_FORCE or fn.lower() in _MALE_FORCE:
        return False
    if fn.lower() in _FEMALE or folded in {_fold(x) for x in _FEMALE}:
        return True
    return False


def royal_title(full_name: str) -> str:
    """Erkek → kral, kadın → kraliçe."""
    return "kraliçe" if is_female_name(full_name) else "kral"


def talk_royal_title(full_name: str) -> str:
    """Konuşma süresi unvanı."""
    return "kraliçesi" if is_female_name(full_name) else "kralı"
