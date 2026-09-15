from pathlib import Path
import re

from fastapi.testclient import TestClient
from captioning.api import make_app
from captioning.i18n import catalog, translate
from captioning.models import Settings, make_prompt
from captioning.quality import unfinished
from captioning.service import Studio


def test_ui_language_is_persistent_and_does_not_change_recipe_or_prompt(tmp_path):
    studio = Studio(tmp_path)
    studio.save_settings(Settings(trigger="subject", words=70, language="English", learn_attributes=["identity", "hair"]))
    before = studio.settings.model_dump()
    prompt = make_prompt(studio.settings)
    app = make_app(studio, "test-token", 8888, Path(__file__).parents[1] / "ui")
    with TestClient(app, base_url="http://127.0.0.1:8888") as client:
        client.get("/?token=test-token")
        assert studio.settings.ui_language == "en"
        assert client.post("/api/ui-language", json={"language":"cs"}).status_code == 403
        headers = {"X-Caption-Client":"1"}
        assert client.post("/api/ui-language", json={"language":"cs"}, headers=headers).status_code == 200
        assert studio.settings.model_dump() == {**before, "ui_language":"cs"}
        assert make_prompt(studio.settings) == prompt
        assert Studio(tmp_path).settings.ui_language == "cs"
        assert client.post("/api/ui-language", json={"language":"invalid"}, headers=headers).status_code == 422
        assert studio.settings.ui_language == "cs"
        for language in ("en", "cs"):
            response = client.get(f"/assets/locales/{language}.json")
            assert response.status_code == 200 and "messages" in response.json()


def test_interface_language_does_not_change_fibo_schema_or_caption_language():
    for output_format in ("normal", "bria_json"):
        settings = Settings(output_format=output_format, language="Czech")
        assert make_prompt(settings) == make_prompt(settings.model_copy(update={"ui_language":"cs"}))


def test_localization_tokens_match_and_czech_is_only_in_locale_resources():
    messages = catalog("cs")["messages"]
    for source, target in messages.items():
        assert sorted(re.findall(r"\{\w+\}", source)) == sorted(re.findall(r"\{\w+\}", target)), source
    assert translate("Select images", "cs") == messages["Select images"]
    assert translate("Select images") == "Select images"
    root = Path(__file__).parents[1]
    files = [root / "app.py", root / "run.bat"]
    for folder in ("captioning", "ui", "scripts", "tests", "installer"):
        files += [p for p in (root/folder).rglob("*") if p.suffix in (".py", ".js", ".html", ".css", ".ps1", ".iss")]
    for path in files:
        assert not re.search("[\u010d\u010f\u011b\u0148\u0159\u0165\u016f\u017e\u0161]", path.read_text(encoding="utf-8").lower()), path


def test_language_resources_preserve_unicode_completion_checks():
    assert unfinished("A person with a blue coat and", finish_reason="stop")
    for word in catalog("cs")["grammar"]["dangling_words"]:
        assert unfinished("Subject " + word, finish_reason="stop")
    assert not unfinished("A person with a blue coat.")
