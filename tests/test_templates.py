from pathlib import Path

import jobber.docker_templates as tpl


def test_list_and_get_templates():
    templates = tpl.list_templates()
    names = {t.name for t in templates}
    assert "cpu" in names
    assert "gpu-cu121" in names
    cpu = tpl.get_template("cpu")
    assert "FROM python" in cpu.content


def test_add_and_delete_template(tmp_path):
    custom_src = tmp_path / "custom.Dockerfile"
    custom_src.write_text("FROM scratch\n")
    tpl.add_template("custom", custom_src)
    added = tpl.get_template("custom")
    assert "FROM scratch" in added.content
    tpl.delete_template("custom")
    try:
        tpl.get_template("custom")
    except ValueError:
        pass
    else:
        raise AssertionError("Template not deleted")
