"""タスク定義（データセット・ラベル・プロンプト）とデータセットの読み込み。"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "tasks"
# Jev / Laya に渡す state の形（task.toml の state_format）。
# "object" = {"log": テキスト}（既定）、"string" = テキストそのもの（jevbench と同じ）
STATE_FORMATS = ("object", "string")
# prompt.md のテンプレートを system / user メッセージに分ける見出し行。無ければ全体が user メッセージ
SYSTEM_HEADER = "[system]"
USER_HEADER = "[user]"


@dataclass(frozen=True)
class Label:
    name: str
    description: str


@dataclass(frozen=True)
class Record:
    id: str
    text: str
    label: str


@dataclass(frozen=True)
class Task:
    name: str
    dataset: Path
    labels: list[Label]
    instructions: str
    prompt_template: str  # user メッセージのテンプレート
    state_format: str = "object"  # STATE_FORMATS のいずれか。LLM のプロンプトには影響しない
    system_template: str | None = None  # system メッセージのテンプレート（prompt.md に [system] がある場合）

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]

    def _render(self, template: str, log: str) -> str:
        labels = "\n".join(f"- {l.name}: {l.description}" for l in self.labels)
        # str.format だとテンプレート中の { } （JSON の出力例など）で壊れるため単純置換
        return (
            template.replace("{instructions}", self.instructions)
            .replace("{labels}", labels)
            .replace("{log}", log)
        )

    def render_prompt(self, log: str) -> str:
        """user メッセージ。"""
        return self._render(self.prompt_template, log)

    def render_system(self) -> str | None:
        """system メッセージ（無ければ None）。分類するテキストは入れない。"""
        if self.system_template is None:
            return None
        return self._render(self.system_template, "")

    def criteria(self) -> dict[str, str]:
        """Jev / Laya の choice 質問に渡す {ラベル名: 説明}。LLM プロンプトの {labels} と同じ内容。"""
        return {l.name: l.description for l in self.labels}


def load_task(name: str) -> Task:
    task_dir = TASKS_DIR / name
    with open(task_dir / "task.toml", "rb") as f:
        raw = tomllib.load(f)
    labels = [Label(**item) for item in raw["labels"]]
    names = [l.name for l in labels]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate label names in {task_dir}/task.toml")
    # 未知の値（typo など）は、Jev / Laya を呼び始める前にここで止める
    state_format = raw.get("state_format", "object")
    if state_format not in STATE_FORMATS:
        raise ValueError(
            f"{task_dir}/task.toml: state_format must be one of "
            f"{', '.join(repr(f) for f in STATE_FORMATS)} (got {state_format!r})"
        )
    # prompt.md は最初の "---" 行以降をテンプレートとして扱う
    text = (task_dir / "prompt.md").read_text(encoding="utf-8")
    if "\n---\n" not in text:
        raise ValueError(f"{task_dir}/prompt.md must separate notes and template with '---'")
    prompt = text.split("\n---\n", 1)[1].strip()
    system, user = _split_prompt(prompt, task_dir)
    return Task(
        name=name,
        dataset=REPO_ROOT / raw["dataset"],
        labels=labels,
        instructions=raw["instructions"],
        prompt_template=user,
        state_format=state_format,
        system_template=system,
    )


def _split_prompt(prompt: str, task_dir: Path) -> tuple[str | None, str]:
    """テンプレートを (system, user) に分ける。見出しが無ければ全体を user とする。

    分ける場合は "[system]" 行で始め、"[user]" 行で user に切り替える。
    """
    lines = prompt.split("\n")
    if SYSTEM_HEADER not in lines and USER_HEADER not in lines:
        return None, prompt
    if lines[0] != SYSTEM_HEADER or lines.count(SYSTEM_HEADER) != 1 or lines.count(USER_HEADER) != 1:
        raise ValueError(
            f"{task_dir}/prompt.md: split the template as '{SYSTEM_HEADER}' (first line) "
            f"then '{USER_HEADER}', each exactly once"
        )
    i = lines.index(USER_HEADER)
    system = "\n".join(lines[1:i]).strip()
    user = "\n".join(lines[i + 1:]).strip()
    if not system or not user:
        raise ValueError(f"{task_dir}/prompt.md: system and user templates must not be empty")
    return system, user


def load_dataset(path: Path, label_names: list[str] | None = None) -> list[Record]:
    """JSONL を読む。label_names を渡すと正解ラベルがタスク定義内にあるかも検証する。

    定義外のラベル（"Payment" などの表記ゆれ）は全モデルで必ず不正解になり、
    per_class にも現れないため Acc と Macro-F1 が食い違う。黙って評価せず行番号付きで止める。
    """
    records: list[Record] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            where = f"{path}:{lineno}"
            try:
                record = Record(**json.loads(line))
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"{where}: invalid record ({e})") from e
            if label_names is not None and record.label not in label_names:
                raise ValueError(f"{where}: unknown label {record.label!r}")
            if record.id in seen:
                raise ValueError(f"{where}: duplicate id {record.id!r}")
            seen.add(record.id)
            records.append(record)
    return records
