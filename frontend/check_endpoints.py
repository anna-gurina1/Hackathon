"""
Checks that the frontend templates match the real backend.

Run from the project root (D:\\Hackathon):
    python frontend/check_endpoints.py

It prints:
  1) url_for('...') names used in templates that the backend does NOT have,
  2) templates the backend renders that are missing in frontend/templates.
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_FOLDER = PROJECT_ROOT / "frontend" / "templates"
BACKEND_FOLDER = PROJECT_ROOT / "backend"

sys.path.insert(0, str(PROJECT_ROOT))
from core import create_app  # noqa: E402

app = create_app()
backend_endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

# ---------- 1. url_for names in templates ----------
url_for_pattern = re.compile(r"url_for\(\s*['\"]([\w.]+)['\"]")
missing_endpoints = {}

for template_file in TEMPLATES_FOLDER.rglob("*.html"):
    for line_number, line in enumerate(template_file.read_text(encoding="utf-8").splitlines(), start=1):
        for endpoint in url_for_pattern.findall(line):
            if endpoint != "static" and endpoint not in backend_endpoints:
                where = f"{template_file.relative_to(PROJECT_ROOT)}:{line_number}"
                missing_endpoints.setdefault(endpoint, []).append(where)

# ---------- 2. templates the backend renders ----------
render_pattern = re.compile(r"render_template\(\s*['\"]([\w/.-]+\.html)['\"]")
missing_templates = {}

for python_file in BACKEND_FOLDER.rglob("*.py"):
    for template_name in render_pattern.findall(python_file.read_text(encoding="utf-8")):
        if not (TEMPLATES_FOLDER / template_name).exists():
            missing_templates.setdefault(template_name, []).append(str(python_file.relative_to(PROJECT_ROOT)))

# ---------- Report ----------
print("\n=== Endpoints in the backend ===")
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.endpoint):
    print(f"  {rule.endpoint:<28} {rule.rule}")

print("\n=== Used in templates, but NOT in the backend ===")
if missing_endpoints:
    for endpoint, places in sorted(missing_endpoints.items()):
        print(f"  {endpoint}  <- {', '.join(places)}")
else:
    print("  none - OK")

print("\n=== Rendered by the backend, but NO template file ===")
if missing_templates:
    for template_name, files in sorted(missing_templates.items()):
        print(f"  {template_name}  <- {', '.join(sorted(set(files)))}")
else:
    print("  none - OK")
