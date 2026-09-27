import os

from hellow_jev.envfile import load_env_file


def test_load_env_file(tmp_path, monkeypatch):
    for key in ("A_KEY", "B_KEY", "C_KEY", "EMPTY_KEY", "PRESET_KEY"):
        monkeypatch.setenv(key, "")  # テスト後に元へ戻すため一度登録してから消す
        monkeypatch.delenv(key)
    monkeypatch.setenv("PRESET_KEY", "from-shell")
    path = tmp_path / ".env"
    path.write_text(
        "# comment\n\nA_KEY=a\nexport B_KEY = 'b c'\nC_KEY=\"x=y\"\nEMPTY_KEY=\nPRESET_KEY=from-file\n"
    )
    assert load_env_file(path) == ["A_KEY", "B_KEY", "C_KEY"]
    assert os.environ["A_KEY"] == "a"
    assert os.environ["B_KEY"] == "b c"
    assert os.environ["C_KEY"] == "x=y"
    assert "EMPTY_KEY" not in os.environ
    assert os.environ["PRESET_KEY"] == "from-shell"


def test_missing_file_is_ignored(tmp_path):
    assert load_env_file(tmp_path / "nope") == []
