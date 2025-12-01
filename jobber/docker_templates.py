"""
Dockerfile template loader for jobber.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List


TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class DockerTemplate:
    name: str
    path: Path

    @property
    def content(self) -> str:
        return self.path.read_text()


def list_templates() -> List[DockerTemplate]:
    templates = []
    for p in TEMPLATES_DIR.glob("*.Dockerfile"):
        templates.append(DockerTemplate(name=p.stem, path=p))
    return templates


def get_template(name: str) -> DockerTemplate:
    p = TEMPLATES_DIR / f"{name}.Dockerfile"
    if not p.exists():
        raise ValueError(f"Unknown template: {name}")
    return DockerTemplate(name=name, path=p)


def add_template(name: str, source_path: Path) -> None:
    dest = TEMPLATES_DIR / f"{name}.Dockerfile"
    dest.write_text(Path(source_path).read_text())


def delete_template(name: str) -> None:
    p = TEMPLATES_DIR / f"{name}.Dockerfile"
    if p.exists():
        p.unlink()
    else:
        raise ValueError(f"Unknown template: {name}")


def search_templates(query: str) -> List[DockerTemplate]:
    return [t for t in list_templates() if query.lower() in t.name.lower()]
