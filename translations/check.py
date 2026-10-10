"""Shows which texts of the site have no translation yet.

    python translations/check.py          all languages (now only ru)

It finds every _("..."), _n(...), _html("...") in templates and Python files,
every t('...') / tn(...) in frontend/static/js, plus the texts from
core/questions.py and backend/plans.py, and compares them with translations/<lang>/*.json.

Texts used in JS must be in scripts.json (only that file is sent to the browser).
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# _("text") / _html("text") / _n(count, "one", "many") in templates
TEMPLATE_TEXT = re.compile(r"""\b_(?:html)?\(\s*(["'])(.*?)\1""", re.S)
TEMPLATE_PLURAL = re.compile(r"""\b_n\(\s*[^,]+?,\s*(["'])(.*?)\1\s*,\s*(["'])(.*?)\3""", re.S)
# t('text') / tn(count, 'one', 'many') in JS
SCRIPT_TEXT = re.compile(r"""\bt\(\s*(['"])(.*?)\1""", re.S)
SCRIPT_PLURAL = re.compile(r"""\btn\(\s*[^,]+?,\s*(['"])(.*?)\1\s*,\s*(['"])(.*?)\3""", re.S)
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def files(folder, ending):
    for path, _dirs, names in os.walk(os.path.join(ROOT, folder)):
        for name in names:
            if name.endswith(ending):
                yield os.path.join(path, name)


def read(path):
    with open(path, encoding="utf-8") as file:
        return file.read()


def python_texts(path):
    """Literal first arguments of _() and the two texts of _n() in a .py file."""
    found = {}
    for node in ast.walk(ast.parse(read(path))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        name, args = node.func.id, node.args
        if name in ("_", "_html", "translate") and args and isinstance(args[0], ast.Constant):
            found[args[0].value] = "text"
        if name == "_n" and len(args) >= 3 and isinstance(args[1], ast.Constant):
            found[args[1].value] = "plural"
    return found


def site_texts():
    """{text: "text" | "plural"} for templates + Python, and the same for JS."""
    texts, script_texts = {}, {}

    for path in files("frontend/templates", ".html"):
        source = read(path)
        for match in TEMPLATE_TEXT.finditer(source):
            texts[match.group(2)] = "text"
        for match in TEMPLATE_PLURAL.finditer(source):
            texts[match.group(2)] = "plural"

    for folder in ("backend", "core", "database"):
        for path in files(folder, ".py"):
            texts.update(python_texts(path))

    # texts that come from data and are translated with _(variable)
    from backend.plans import PLAN_LABELS
    from core.questions import CATEGORIES, LEVELS, QUESTIONS, QUIZ_TEMPLATES

    for question in QUESTIONS:
        if question["answer_type"] == "media":  # only these are shown on the site
            texts[question["text"]] = "text"
            texts[question["hint"]] = "text"
    texts["Please log in to continue."] = "text"  # core/__init__.py, login_manager.login_message
    for label in [*CATEGORIES.values(), *LEVELS.values(), *PLAN_LABELS.values()]:
        texts[label] = "text"
    for suggestions in QUIZ_TEMPLATES.values():
        for suggestion in suggestions:
            texts[suggestion] = "text"

    for path in files("frontend/static/js", ".js"):
        source = read(path)
        if path.endswith("main.js"):  # the examples in the comments of t() itself
            source = source.split("// ---------- Login", 1)[-1]
        for match in SCRIPT_TEXT.finditer(source):
            script_texts[match.group(2)] = "text"
        for match in SCRIPT_PLURAL.finditer(source):
            script_texts[match.group(2)] = "plural"

    return texts, script_texts


def load(language):
    folder = os.path.join(ROOT, "translations", language)
    merged, scripts = {}, {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            data = json.loads(read(os.path.join(folder, name)))
            merged.update(data)
            if name == "scripts.json":
                scripts = data
    return merged, scripts


def problems(texts, dictionary, where):
    found = []
    for text, kind in sorted(texts.items()):
        translated = dictionary.get(text)
        if translated is None:
            found.append(f"  missing ({where}): {text!r}")
            continue
        forms = translated if isinstance(translated, list) else [translated]
        if kind == "plural" and len(forms) != 3:
            found.append(f"  needs 3 forms (1 / 2 / 5): {text!r}")
        for form in forms:
            if set(PLACEHOLDER.findall(form)) - set(PLACEHOLDER.findall(text)) - {"count"}:
                found.append(f"  unknown {{placeholder}} in the translation of {text!r}: {form!r}")
    return found


def main():
    texts, script_texts = site_texts()
    exit_code = 0
    for language in sorted(os.listdir(os.path.join(ROOT, "translations"))):
        if language.startswith(("_", ".")) or not os.path.isdir(os.path.join(ROOT, "translations", language)):
            continue  # __pycache__ and other service folders are not languages
        dictionary, scripts = load(language)
        found = problems(texts, dictionary, "any file") + problems(script_texts, scripts, "scripts.json")
        unused = sorted(set(dictionary) - set(texts) - set(script_texts))
        print(f"[{language}] texts on the site: {len(texts) + len(script_texts)}, problems: {len(found)}")
        if found:
            print("\n".join(found))
        if unused:
            print(f"  not used anywhere (can be deleted): {len(unused)}")
            for text in unused:
                print(f"    {text!r}")
        exit_code = exit_code or (1 if found else 0)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
