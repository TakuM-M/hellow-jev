"""configs/*.toml が実行時と同じ手順で分類器まで組み立てられるか（実行前に typo を見つける）。"""

import tomllib

import pytest

from hellow_jev.classifiers import build_classifier
from hellow_jev.run import NAME_RE, available_tasks
from hellow_jev.task import REPO_ROOT, load_task

CONFIGS = sorted((REPO_ROOT / "configs").glob("*.toml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_config_builds(path, monkeypatch):
    # API キーは実行時に環境変数から読むので、ダミーで与える（接続はしない）
    monkeypatch.setenv("JEV_API_KEY", "k")
    monkeypatch.setenv("LLM_API_KEY", "k")
    with open(path, "rb") as f:
        config = tomllib.load(f)
    # report は <name>.toml の [pricing] を読むので、ファイル名と name を揃える
    assert config["name"] == path.stem and NAME_RE.fullmatch(config["name"])
    assert config["task"] in available_tasks()
    assert isinstance(config["warmup"], int) and config["warmup"] >= 0
    assert isinstance(config["hardware"], str) and config["hardware"]
    assert set(config["pricing"]) == {"input_per_mtok", "output_per_mtok"}
    build_classifier(config["classifier"], load_task(config["task"]))
