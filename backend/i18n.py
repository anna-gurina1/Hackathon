"""Switching the site between English and Russian.

How it works:
  * Texts in the code and in the templates stay in English.
  * Russian translations live in translations/ru/*.json as  "English text": "Русский текст".
  * _("English text") returns the text in the visitor's language.
    If a translation is missing, the English text is shown, so the site never breaks.

Where the chosen language is remembered:
  1. the "lang" cookie in the browser (works for guests too);
  2. User.language in the database (emails to this person come in their language,
     and the choice follows them to another device after logging in);
  3. if neither is set: the browser language (Accept-Language), otherwise English.

Used in templates:
    {{ _("Log in") }}
    {{ _("Lesson {number} of {total}", number=n, total=course.lesson_count) }}
    {{ _n(count, "{count} lesson", "{count} lessons") }}       -> 1 урок / 2 урока / 5 уроков
    {{ _html("You finished <strong>{course}</strong>", course=course.title) }}   (HTML inside)
    {{ format_date(offer.created_at) }}
In Python:  from backend.i18n import _
In JS:      t("Copied ✓"), tn(count, "{count} course", "{count} courses")   (main.js)

To translate a new text: wrap it in _() and add the line to translations/ru/*.json.
See what is missing:  python translations/check.py
"""
import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar

from flask import g, has_request_context, request
from markupsafe import Markup, escape

from core.config import BASE_DIR

LANGUAGES = {"en": "English", "ru": "Русский"}
DEFAULT_LANGUAGE = "en"
COOKIE_NAME = "lang"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # one year

TRANSLATIONS_DIR = os.path.join(BASE_DIR, "translations")
SCRIPTS_FILE = "scripts.json"  # the only file that is sent to the browser (texts used in JS)

# Russian month names for dates: "9 октября 2026"
RUSSIAN_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

log = logging.getLogger(__name__)

# Set by use_language(): the language of an email to another person
_forced_language = ContextVar("forced_language", default=None)

# {"ru": (file signature, {english: russian})}. Reloaded when a .json file changes,
# so you can fix a translation without restarting the server.
_cache = {}


# ---------- loading the dictionaries ----------

def _json_files(language):
    folder = os.path.join(TRANSLATIONS_DIR, language)
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, name) for name in os.listdir(folder) if name.endswith(".json"))


def _load_dictionary(language):
    """All translations of a language: the .json files of its folder merged into one dict."""
    files = _json_files(language)
    signature = tuple((path, os.path.getmtime(path)) for path in files)
    cached = _cache.get(language)
    if cached and cached[0] == signature:
        return cached[1]

    merged = {}
    for path in files:
        try:
            with open(path, encoding="utf-8") as file:
                merged.update(json.load(file))
        except (OSError, ValueError):
            # a typo in one file must not take the site down: that file is just skipped
            log.exception("Could not read the translation file %s", path)
    _cache[language] = (signature, merged)
    return merged


def _dictionary(language):
    """Same as _load_dictionary, but checked only once per page."""
    if not has_request_context():
        return _load_dictionary(language)
    loaded = g.setdefault("_translations", {})
    if language not in loaded:
        loaded[language] = _load_dictionary(language)
    return loaded[language]


def scripts_dictionary():
    """Translations for JS (only translations/<lang>/scripts.json), put into every page."""
    language = current_language()
    path = os.path.join(TRANSLATIONS_DIR, language, SCRIPTS_FILE)
    if language == DEFAULT_LANGUAGE or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        log.exception("Could not read the translation file %s", path)
        return {}


# ---------- which language ----------

def chosen_language():
    """The language the visitor chose with the EN / RU switch (cookie), or None."""
    if not has_request_context():
        return None
    language = request.cookies.get(COOKIE_NAME)
    return language if language in LANGUAGES else None


def _detect_language():
    language = chosen_language()
    if language:
        return language

    from flask_login import current_user

    saved = getattr(current_user, "language", None) if current_user else None
    if saved in LANGUAGES:
        return saved
    return request.accept_languages.best_match(list(LANGUAGES)) or DEFAULT_LANGUAGE


def current_language():
    """"en" or "ru"."""
    forced = _forced_language.get()
    if forced:
        return forced
    if not has_request_context():
        return DEFAULT_LANGUAGE
    if "language" not in g:
        g.language = _detect_language()
    return g.language


@contextmanager
def use_language(language):
    """Temporarily switch the language, e.g. for an email to another person:

        with use_language(person.language):
            send_email(person.email, _("Your request"), ...)
    """
    token = _forced_language.set(language if language in LANGUAGES else DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        _forced_language.reset(token)


# ---------- translating ----------

def _russian_plural_form(count):
    """0 = 1 урок, 1 = 2 урока, 2 = 5 уроков."""
    count = abs(int(count))
    if count % 10 == 1 and count % 100 != 11:
        return 0
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return 1
    return 2


PLURAL_RULES = {"ru": _russian_plural_form}


def _fill(text, english, values):
    """Put the values into {placeholders}. A broken translation falls back to English."""
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        log.warning("Broken placeholders in the translation of %r", english)
        return english.format(**values)


def _lookup(text):
    language = current_language()
    if language == DEFAULT_LANGUAGE:
        return text
    translated = _dictionary(language).get(text)
    if isinstance(translated, list):  # plural forms, but used without a number
        translated = translated[0] if translated else None
    return translated or text


def _(text, **values):
    """Text in the current language. _("Hi {name}", name="Anna")"""
    return _fill(_lookup(text), text, values)


def _n(count, singular, plural, **values):
    """Text with a number: _n(5, "{count} lesson", "{count} lessons") -> "5 уроков".
    In translations/ru the key is the singular text and the value is a list of 3 forms:
        "{count} lesson": ["{count} урок", "{count} урока", "{count} уроков"]
    """
    values.setdefault("count", count)
    english = singular if count == 1 else plural
    language = current_language()
    forms = _dictionary(language).get(singular) if language != DEFAULT_LANGUAGE else None

    if isinstance(forms, list) and forms and language in PLURAL_RULES:
        text = forms[min(PLURAL_RULES[language](count), len(forms) - 1)]
    elif isinstance(forms, str) and forms:
        text = forms
    else:
        text = english
    return _fill(text, english, values)


def _html(text, **values):
    """For templates only: the translation may contain HTML (<strong>, <a>).
    The values are escaped, so a course title can never become HTML."""
    translated = _lookup(text)
    try:
        return Markup(translated).format(**{key: escape(value) for key, value in values.items()})
    except (KeyError, IndexError, ValueError):
        log.warning("Broken placeholders in the translation of %r", text)
        return Markup(text).format(**{key: escape(value) for key, value in values.items()})


def format_date(moment):
    """Oct 09, 2026 / 9 октября 2026"""
    if moment is None:
        return ""
    if current_language() == "ru":
        return f"{moment.day} {RUSSIAN_MONTHS[moment.month - 1]} {moment.year}"
    return moment.strftime("%b %d, %Y")


def safe_next_url(url, fallback="/"):
    """Only a path on our own site (protects the language switch from redirects to other sites)."""
    if not url or not url.startswith("/") or url.startswith("//") or "\\" in url:
        return fallback
    return url


def init_app(app):
    """Make _, _n, _html, format_date and the language available in every template."""
    app.jinja_env.globals.update(
        _=_,
        _n=_n,
        _html=_html,
        format_date=format_date,
        current_language=current_language,
        LANGUAGES=LANGUAGES,
        scripts_dictionary=scripts_dictionary,
    )
