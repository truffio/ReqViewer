"""Fill the page template with the data."""
import json
from pathlib import Path

PLACEHOLDER = "/*DATA*/null"


def render(data):
    template = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload, 1)
