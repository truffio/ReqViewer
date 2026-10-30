"""Fill the page template with the data."""
import json
from pathlib import Path

PLACEHOLDER = "/*DATA*/null"


def render(data):
    template = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    # The data goes in as JSON text inside a JS string literal, read by JSON.parse in the page, because an
    # object literal would treat a "__proto__" key as the prototype. The literal is ASCII (ensure_ascii), so
    # a lone surrogate cannot break the write, and has no "<", so nothing in the data can close the script.
    literal = json.dumps(json.dumps(data, ensure_ascii=True), ensure_ascii=True).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, f"JSON.parse({literal})", 1)
