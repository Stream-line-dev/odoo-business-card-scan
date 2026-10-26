# -*- coding: utf-8 -*-
"""Analyse du texte brut d'une carte de visite (résultat OCR).

Module Python pur (aucun import Odoo) pour pouvoir être testé seul :
    python3 -m unittest business_card_scan.tests.test_card_parser
"""
import re
import unicodedata

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
URL_RE = re.compile(
    r"\b((?:https?://)?(?:www\.)[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+(?:/\S*)?"
    r"|(?:https?://)[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+(?:/\S*)?"
    r"|[A-Za-z0-9\-]+\.(?:com|ma|fr|net|org|io|co|ca|be|ch|de|es|it|uk|eu|tn|dz|info|biz|tech|app|dev)(?:/\S*)?)\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?:\+|00)?\(?\d[\d\s().\-/]{6,}\d")

LABEL_RE = re.compile(
    r"^\s*(?:(?:t[ée]l[ée]?(?:phone)?|tel|phone|ph|mobile?|mob|gsm|portable|cell(?:ular)?|office|direct|main|"
    r"fixe|fax|e-?mail|mail|courriel|web|site|website|adresse|address|addr|"
    r"[tmcpofew](?=\s*[.:]))\s*[.:/]*\s*)+",
    re.IGNORECASE,
)

GENERIC_DOMAINS = {
    "gmail", "yahoo", "hotmail", "outlook", "live", "icloud", "menara", "aol",
    "gmx", "protonmail", "proton", "msn", "orange", "free", "wanadoo", "yandex",
}

COMPANY_HINTS = (
    "sarl", "s.a.r.l", "sarlau", "sa", "s.a", "sas", "sasu", "eurl", "snc",
    "ltd", "ltée", "ltee", "llc", "llp", "inc", "corp", "corporation", "co.", "plc",
    "gmbh", "group", "groupe", "holding", "holdings", "enterprises", "partners",
    "associates", "logistics", "manufacturing", "foods", "realty",
    "company", "société", "societe", "consulting", "solutions", "services",
    "technologies", "technology", "industries", "industry", "international",
    "agency", "agence", "cabinet", "studio", "lab", "labs", "systems",
)

JOB_HINTS = (
    "directeur", "directrice", "director", "manager", "gérant", "gerant", "gérante",
    "responsable", "chef", "head", "ceo", "cto", "cfo", "coo", "cmo", "president",
    "président", "présidente", "fondateur", "fondatrice", "founder", "co-founder",
    "ingénieur", "ingenieur", "engineer", "développeur", "developpeur", "developer",
    "consultant", "consultante", "commercial", "commerciale", "sales", "account",
    "assistant", "assistante", "chargé", "chargée", "charge", "attaché", "attachée",
    "conseiller", "conseillère", "technicien", "technicienne", "comptable",
    "analyste", "analyst", "architecte", "architect", "designer", "officer",
    "associé", "associée", "partner", "administrateur", "administrator",
    "délégué", "déléguée", "representative", "représentant", "représentante",
    "coordinateur", "coordinatrice", "coordinator", "superviseur", "supervisor",
    "vp", "vice", "lead", "owner", "propriétaire", "dg", "pdg", "rh", "hr",
    "marketing", "achat", "achats", "acheteur", "buyer", "export", "logistique",
    "executive", "specialist", "advisor", "adviser", "senior", "principal",
    "procurement", "purchasing", "operations", "business development", "chairman",
    "secretary", "treasurer", "agent", "broker", "realtor", "accountant", "cpa",
)

ADDRESS_HINTS = (
    "rue", "avenue", "av.", "bd", "bd.", "boulevard", "lot", "lotissement",
    "résidence", "residence", "quartier", "imm", "immeuble", "étage", "etage",
    "n°", "bp", "b.p", "cedex", "zone", "z.i", "zi", "route", "street", "st.",
    "road", "suite", "floor", "angle", "hay", "derb", "appt", "appartement",
    "maroc", "morocco", "france", "canada", "casablanca", "rabat", "marrakech",
    "tanger", "fès", "fes", "agadir", "meknès", "meknes", "oujda", "kénitra",
    "kenitra", "tétouan", "tetouan", "el jadida", "mohammedia", "paris", "lyon",
    "montréal", "montreal", "québec", "quebec",
    "ave", "ave.", "blvd", "blvd.", "drive", "dr.", "lane", "ln.", "way", "court",
    "crescent", "place", "unit", "p.o. box", "po box", "usa", "united states",
    "toronto", "ottawa", "vancouver", "calgary", "edmonton", "winnipeg", "laval",
    "gatineau", "mississauga", "ontario", "alberta", "british columbia",
    "new york", "london", "uk", "united kingdom",
)


def _norm(text):
    """Minuscules sans accents, pour comparer des mots."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _words(line):
    # Garde les apostrophes et tirets internes : O'Brien, Jean-Pierre
    return re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", line)


def _has_hint(line, hints):
    low = " %s " % re.sub(r"[,;|()]", " ", line.lower())
    norm_low = _norm(low)
    for hint in hints:
        h = hint.lower()
        if re.search(r"(?<![\w])%s(?![\w])" % re.escape(h), low) or re.search(
            r"(?<![\w])%s(?![\w])" % re.escape(_norm(h)), norm_low
        ):
            return True
    return False


def _clean_line(line):
    line = line.replace("|", " ").replace("•", " ").replace("·", " ")
    line = re.sub(r"\s+", " ", line).strip(" -–—_*:;,")
    return line


def _fix_email_spacing(text):
    # L'OCR coupe souvent les emails : "nom @ societe . ma"
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"(@[A-Za-z0-9\-]+)\s*\.\s*([A-Za-z]{2,})", r"\1.\2", text)
    return text


def _phone_digits(value):
    return re.sub(r"\D", "", value)


def _clean_phone(value):
    value = value.strip(" .-/")
    value = re.sub(r"\s+", " ", value)
    return value


def _domain_name(email=None, website=None):
    domain = ""
    if email and "@" in email:
        domain = email.split("@", 1)[1]
    elif website:
        domain = re.sub(r"^https?://", "", website, flags=re.I)
        domain = re.sub(r"^www\.", "", domain, flags=re.I).split("/")[0]
    if not domain:
        return ""
    base = domain.split(".")[0]
    if base.lower() in GENERIC_DOMAINS:
        return ""
    return base


def _looks_like_name(line):
    words = _words(line)
    if not 2 <= len(words) <= 4:
        return False
    if re.search(r"\d|@|www|https?:", line, re.I):
        return False
    if len("".join(words)) < len(line.replace(" ", "")) * 0.8:
        return False  # trop de symboles
    if _has_hint(line, JOB_HINTS) or _has_hint(line, COMPANY_HINTS) or _has_hint(line, ADDRESS_HINTS):
        return False
    return all(len(w) >= 2 for w in words)


def _strip_logo_initials(line):
    """Retire les initiales du logo collées par l'OCR : "NL NORTHWIND LOGISTICS" -> "NORTHWIND LOGISTICS"."""
    words = line.split()
    first = words[0] if words else ""
    if 1 <= len(first) <= 3 and first.isalpha() and first.isupper() and len(words) > len(first):
        initials = "".join(w[0] for w in words[1:1 + len(first)])
        if _norm(first) == _norm(initials):
            return " ".join(words[1:])
    return line


def _format_name(line):
    words = line.split()
    if line.isupper():
        return " ".join(w.capitalize() if not w.isupper() or len(w) > 1 else w for w in words).title()
    return " ".join(words)


def parse_card_text(text):
    """Retourne un dict avec les champs détectés sur la carte.

    Clés : contact_name, partner_name, function, email, phone, phone_2,
    website, street, other_lines.
    """
    result = {
        "contact_name": False,
        "partner_name": False,
        "function": False,
        "email": False,
        "phone": False,
        "phone_2": False,
        "website": False,
        "street": False,
        "other_lines": [],
    }
    if not text:
        return result

    text = _fix_email_spacing(text)
    raw_lines = [_clean_line(l) for l in text.splitlines()]
    lines = [l for l in raw_lines if len(l) >= 2]

    used = set()
    phones = []

    # 1) Email
    for i, line in enumerate(lines):
        m = EMAIL_RE.search(line)
        if m:
            if not result["email"]:
                result["email"] = m.group(0).strip(".").lower()
            rest = LABEL_RE.sub("", line.replace(m.group(0), "")).strip(" :-")
            if len(rest) < 3:
                used.add(i)
            else:
                lines[i] = rest

    # 2) Site web
    for i, line in enumerate(lines):
        if i in used:
            continue
        candidate = line.replace(result["email"] or "\x00", " ")
        m = URL_RE.search(candidate)
        if m and "@" not in m.group(0):
            if not result["website"]:
                site = m.group(0).rstrip(".,;/")
                result["website"] = site if site.lower().startswith("http") else "https://" + site.lower()
            rest = LABEL_RE.sub("", candidate.replace(m.group(0), "")).strip(" :-")
            if len(rest) < 3:
                used.add(i)
            else:
                lines[i] = rest

    # 3) Téléphones (on ignore le fax)
    for i, line in enumerate(lines):
        if i in used:
            continue
        found = False
        for m in PHONE_RE.finditer(line):
            digits = _phone_digits(m.group(0))
            if 9 <= len(digits) <= 15:
                found = True
                before = line[: m.start()]
                is_fax = re.search(r"\bfax\b|^\s*f\s*[.:]", before, re.I) and not re.search(
                    r"t[ée]l|gsm|mob|phone|portable|cell", before, re.I
                )
                if not is_fax:
                    is_mobile = bool(re.search(
                        r"gsm|mob|portable|cell|^\s*[mc]\s*[.:]", before, re.I
                    ))
                    phones.append((_clean_phone(m.group(0)), is_mobile))
        if found:
            rest = PHONE_RE.sub("", line)
            rest = LABEL_RE.sub("", rest).strip(" :-/")
            if len(_words(rest)) <= 2 and not _has_hint(rest, ADDRESS_HINTS):
                used.add(i)
            else:
                lines[i] = rest

    # Les portables (06/07, +2126/7, ou libellé GSM/mobile/cell/M:) en premier
    def _mobile_rank(phone):
        value, is_mobile = phone
        d = _phone_digits(value)
        return 0 if is_mobile or re.match(r"^(0[67]|2126|2127|002126|002127)", d) else 1

    phones = list(dict.fromkeys(value for value, _mobile in sorted(phones, key=_mobile_rank)))
    if phones:
        result["phone"] = phones[0]
    if len(phones) > 1:
        result["phone_2"] = phones[1]

    # 4) Adresse
    address_parts = []
    for i, line in enumerate(lines):
        if i in used:
            continue
        if _has_hint(line, ADDRESS_HINTS) and (re.search(r"\d", line) or len(_words(line)) >= 3):
            address_parts.append(LABEL_RE.sub("", line))
            used.add(i)
    if address_parts:
        result["street"] = ", ".join(address_parts[:2])

    # 5) Poste
    job_idx = None
    for i, line in enumerate(lines):
        if i in used:
            continue
        if _has_hint(line, JOB_HINTS) and len(_words(line)) <= 7 and not re.search(r"\d", line):
            result["function"] = line
            job_idx = i
            used.add(i)
            break

    # 6) Société (suffixe juridique / mot-clé)
    company_idx = None
    for i, line in enumerate(lines):
        if i in used:
            continue
        if _has_hint(line, COMPANY_HINTS) and len(_words(line)) <= 6:
            result["partner_name"] = _strip_logo_initials(line)
            company_idx = i
            used.add(i)
            break

    # 7) Nom : on note les lignes candidates
    email_local = _norm((result["email"] or "").split("@")[0])
    email_tokens = {t for t in re.split(r"[._\-]+", email_local) if len(t) >= 2}
    best, best_score = None, -1
    for i, line in enumerate(lines):
        if i in used or not _looks_like_name(line):
            continue
        words = _words(line)
        score = 1
        if all(w[0].isupper() for w in words):
            score += 2
        if job_idx is not None and abs(i - job_idx) == 1:
            score += 3
        if email_tokens & {_norm(w) for w in words}:
            score += 4
        if i <= 2:
            score += 1
        if score > best_score:
            best, best_score = i, score
    if best is not None:
        result["contact_name"] = _format_name(lines[best])
        used.add(best)

    # 8) Société par défaut : ligne en MAJUSCULES restante, sinon domaine de l'email
    if not result["partner_name"]:
        for i, line in enumerate(lines):
            if i in used:
                continue
            letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", line)
            if len(letters) >= 2 and line.isupper() and len(_words(line)) <= 4 and not re.search(r"\d{3,}", line):
                result["partner_name"] = _strip_logo_initials(line)
                used.add(i)
                break
    if not result["partner_name"]:
        domain = _domain_name(result["email"], result["website"])
        if domain:
            result["partner_name"] = domain.upper() if len(domain) <= 4 else domain.capitalize()

    result["other_lines"] = [l for i, l in enumerate(lines) if i not in used and len(l) >= 3]
    return result
