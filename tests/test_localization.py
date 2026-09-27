import ast
import re
from pathlib import Path

from fastapi.testclient import TestClient

from captioning.api import make_app
from captioning.i18n import catalog, translate
from captioning.models import Settings, make_prompt
from captioning.quality import unfinished
from captioning.service import Studio
from captioning.training import ALL_TYPES, details_for

ROOT = Path(__file__).parents[1]
USER_FIELDS = {"message", "notice", "error", "detail"}


def placeholders(text):
    return re.sub(r"\{\w*\}", "{}", text)


def first_argument(source, start):
    """Source text of the first argument of a call whose '(' ends at start."""
    depth, quote, index = 0, None, start
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif char == "," and depth == 0:
            break
        index += 1
    return source[start:index]


def ui_message_ids():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', html))
    for path in (ROOT / "ui").glob("*.js"):
        source = path.read_text(encoding="utf-8")
        for call in re.finditer(r"(?<![\w.$])t\(", source):
            argument = re.sub(r"[=!]==?\s*(['\"])[^'\"]*\1", "", first_argument(source, call.end()))
            ids |= {match[1] for match in re.findall(r"(['\"])((?:(?!\1).)*)\1", argument)}
        for table in re.findall(r"(?:labels|phaseLabels|modelNotes)\s*=\s*\{([^}]*)\}", source):
            ids |= set(re.findall(r":\s*'([^']*)'", table))
    # Every LoRA type names its details in its own way (training.details_for).
    return ids | {
        detail[key] for lora_type in ALL_TYPES for detail in details_for(lora_type) for key in ("label", "detail")
    }


def message_templates(node):
    """Messages an expression can produce, with {} for runtime values."""
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else []
    if isinstance(node, ast.JoinedStr):
        return ["".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)]
    if isinstance(node, ast.IfExp):
        return message_templates(node.body) + message_templates(node.orelse)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [
            left + right
            for left in message_templates(node.left) or ["{}"]
            for right in message_templates(node.right) or ["{}"]
        ]
    return []


def backend_messages():
    """User-visible diagnostics: exception texts and message/notice/error/detail values."""
    for path in [ROOT / "app.py", *(ROOT / "captioning").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            values = []
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                values.append(node.exc.args[0])
            elif isinstance(node, ast.Call):
                values += [keyword.value for keyword in node.keywords if keyword.arg in USER_FIELDS]
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in ("show_message", "translate", "t", "notice")
                    and node.args
                ):
                    values.append(node.args[0])
            elif isinstance(node, ast.Dict):
                values += [
                    value
                    for key, value in zip(node.keys, node.values, strict=True)
                    if isinstance(key, ast.Constant) and key.value in USER_FIELDS
                ]
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(
                    isinstance(t, ast.Name) and t.id.lower().endswith(("hints", "labels")) for t in targets
                ) and isinstance(node.value, ast.Dict):
                    values += node.value.values
                elif any(
                    isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) and t.slice.value in USER_FIELDS
                    for t in targets
                ):
                    values.append(node.value)
            for value in values:
                for text in message_templates(value):
                    if re.search("[A-Za-z]", placeholders(text).replace("{}", "")):
                        yield path.name, text


def test_ui_language_is_persistent_and_does_not_change_recipe_or_prompt(tmp_path):
    studio = Studio(tmp_path)
    studio.save_settings(
        Settings(trigger="subject", words=70, language="English", omitted_attributes=["identity", "hair"])
    )
    before = studio.settings.model_dump()
    prompt = make_prompt(studio.settings)
    app = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        assert studio.settings.ui_language == "en"
        assert client.post("/api/ui-language", json={"language": "cs"}).status_code == 403
        headers = {"X-Caption-Client": "1"}
        assert client.post("/api/ui-language", json={"language": "cs"}, headers=headers).status_code == 200
        assert studio.settings.model_dump() == {**before, "ui_language": "cs"}
        assert make_prompt(studio.settings) == prompt
        assert Studio(tmp_path).settings.ui_language == "cs"
        assert client.post("/api/ui-language", json={"language": "invalid"}, headers=headers).status_code == 422
        assert studio.settings.ui_language == "cs"
        for language in ("en", "cs"):
            response = client.get(f"/assets/locales/{language}.json")
            assert response.status_code == 200 and "messages" in response.json()


def test_interface_language_does_not_change_fibo_schema_or_caption_language():
    for output_format in ("normal", "bria_json"):
        settings = Settings(output_format=output_format, language="Czech")
        assert make_prompt(settings) == make_prompt(settings.model_copy(update={"ui_language": "cs"}))


def test_localization_tokens_match_and_czech_is_only_in_locale_resources():
    messages = catalog("cs")["messages"]
    for source, target in messages.items():
        # A Czech value may carry the three count forms as "one|few|many"; each keeps the same values.
        for variant in target.split("|"):
            assert sorted(re.findall(r"\{\w+\}", source)) == sorted(re.findall(r"\{\w+\}", variant)), source
    assert translate("Select images", "cs") == messages["Select images"]
    assert translate("Select images") == "Select images"
    root = Path(__file__).parents[1]
    files = [root / "app.py", root / "run.bat"]
    for folder in ("captioning", "ui", "scripts", "tests", "installer"):
        files += [p for p in (root / folder).rglob("*") if p.suffix in (".py", ".js", ".html", ".css", ".ps1", ".iss")]
    for path in files:
        assert not re.search(
            "[\u010d\u010f\u011b\u0148\u0159\u0165\u016f\u017e\u0161]", path.read_text(encoding="utf-8").lower()
        ), path


def test_every_ui_message_has_a_czech_translation():
    messages = catalog("cs")["messages"]
    ids = ui_message_ids()
    assert {"Captioning…", "Select {name}", "Model and runtime", "Caption"} <= ids  # extraction sanity
    assert sorted(ids - messages.keys()) == []


def test_backend_diagnostics_can_be_translated():
    messages = catalog("cs")["messages"]
    templates = {placeholders(key) for key in messages}
    found = list(backend_messages())
    assert ("service.py", "Batch paused: {}") in found  # extraction sanity
    missing = [(name, text) for name, text in found if text not in messages and placeholders(text) not in templates]
    assert missing == []


def test_language_resources_preserve_unicode_completion_checks():
    assert unfinished("A person with a blue coat and", finish_reason="stop")
    for word in catalog("cs")["grammar"]["dangling_words"]:
        assert unfinished("Subject " + word, finish_reason="stop")
    assert not unfinished("A person with a blue coat.")


def test_ui_modules_are_served_as_javascript(tmp_path):
    app = make_app(Studio(tmp_path), "test-token", 8888, ROOT / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        assert '<script type="module" src="/assets/main.js">' in client.get("/?token=test-token").text
        for path in (ROOT / "ui").glob("*.js"):
            assert client.get("/assets/" + path.name).headers["content-type"].startswith("text/javascript"), path
        assert client.get("/assets/style.css").headers["content-type"].startswith("text/css")
