"""分類器の登録と生成。"""

from __future__ import annotations

from typing import Any

from hellow_jev.classifiers.base import Classifier, Prediction
from hellow_jev.classifiers.baseline import KeywordBaseline
from hellow_jev.classifiers.jev import JevClassifier
from hellow_jev.classifiers.laya import LayaClassifier
from hellow_jev.classifiers.llm import LLMClassifier
from hellow_jev.task import Task

REGISTRY: dict[str, type[Classifier]] = {
    "baseline": KeywordBaseline,
    "jev": JevClassifier,
    "laya": LayaClassifier,
    "llm": LLMClassifier,
}


def build_classifier(config: dict[str, Any], task: Task) -> Classifier:
    options = dict(config)
    kind = options.pop("type")
    return REGISTRY[kind](task, **options)


__all__ = ["Classifier", "Prediction", "REGISTRY", "build_classifier"]
