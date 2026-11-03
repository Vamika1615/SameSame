import pytest

from samesame import config


@pytest.fixture(autouse=True)
def isolated_build_dir(tmp_path, monkeypatch):
    """Tests never write into the real data/build (review labels are training data)."""
    monkeypatch.setattr(config, "BUILD", tmp_path)
