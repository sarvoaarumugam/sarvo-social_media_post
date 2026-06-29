"""Loads prompt templates from the top-level `prompts/` folder.

Prompts are grouped by stage into YAML files (e.g. `script.yaml`, `audio.yaml`).
Each top-level key in a file is one prompt with `$name` placeholders. Files are
read fresh on each call so edits take effect immediately — handy while tuning and
cheap compared to an LLM request.

    render("script", "system", brand="...", host1="Anna", ...)
"""

from pathlib import Path
from string import Template

import yaml

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def render(file: str, key: str, **values: object) -> str:
    """Render prompt `key` from `prompts/<file>.yaml` with its placeholders filled.

    Raises KeyError if the file lacks the key, or if the template references a
    placeholder we didn't provide — so mistakes fail loudly instead of shipping a
    broken prompt.
    """
    data = yaml.safe_load((PROMPTS_DIR / f"{file}.yaml").read_text(encoding="utf-8"))
    if key not in data:
        raise KeyError(f"Prompt key '{key}' not found in prompts/{file}.yaml")
    template = data[key]
    if isinstance(template, dict):  # tolerate {description, template} form too
        template = template["template"]
    return Template(template).substitute(**values)
