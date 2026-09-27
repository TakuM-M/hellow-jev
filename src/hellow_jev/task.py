"""タスク定義（データセット・ラベル・プロンプト）とデータセットの読み込み。"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "tasks"


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
    name: str
    dataset: Path
    default_label: str
    labels: list[Label]
    prompt_template: str

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]

    def render_prompt(self, log: str) -> str:
        labels = "\n".join(f"- {l.name}: {l.description}" for l in self.labels)
        # str.format だとテンプレート中の { } （JSON の出力例など）で壊れるため単純置換
        return self.prompt_template.replace("{labels}", labels).replace("{log}", log)


def load_task(name: str) -> Task:
    task_dir = TASKS_DIR / name
    with open(task_dir / "task.toml", "rb") as f:
        raw = tomllib.load(f)
    labels = [Label(**item) for item in raw["labels"]]
    names = [l.name for l in labels]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate label names in {task_dir}/task.toml")
    if raw["default_label"] not in names:
        raise ValueError(f"default_label {raw['default_label']!r} is not a defined label")
    # prompt.md は最初の "---" 行以降をテンプレートとして扱う
    text = (task_dir / "prompt.md").read_text(encoding="utf-8")
    if "\n---\n" not in text:
        raise ValueError(f"{task_dir}/prompt.md must separate notes and template with '---'")
    prompt = text.split("\n---\n", 1)[1].strip()
    return Task(
        name=name,
        dataset=REPO_ROOT / raw["dataset"],
        default_label=raw["default_label"],
        labels=labels,
        prompt_template=prompt,
    )


def load_dataset(path: Path) -> list[Record]:
    with open(path, encoding="utf-8") as f:
        return [Record(**json.loads(line)) for line in f if line.strip()]
