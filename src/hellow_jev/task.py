"""タスク定義（ラベル・プロンプト）とデータセットの読み込み。"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Label:
    name: str
    description: str
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Record:
    id: str
    text: str
    label: str


@dataclass(frozen=True)
class Task:
    labels: list[Label]
    prompt_template: str

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]

    def render_prompt(self, log: str) -> str:
        labels = "\n".join(f"- {l.name}: {l.description}" for l in self.labels)
        return self.prompt_template.format(labels=labels, log=log)


def load_task(task_dir: Path) -> Task:
    with open(task_dir / "labels.toml", "rb") as f:
        raw = tomllib.load(f)
    labels = [Label(**item) for item in raw["labels"]]
    # prompt.md は "---" 以降をテンプレートとして扱う
    prompt = (task_dir / "prompt.md").read_text(encoding="utf-8").split("\n---\n", 1)[-1].strip()
    return Task(labels=labels, prompt_template=prompt)


def load_dataset(path: Path) -> list[Record]:
    with open(path, encoding="utf-8") as f:
        return [Record(**json.loads(line)) for line in f if line.strip()]
