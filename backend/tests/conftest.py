import pytest

from samesame import config, pipeline, store


def pytest_sessionstart(session):
    """The API reads data/build; build it once (without images, ~5 s) if this checkout has never run the pipeline."""
    if not store.ready():
        pipeline.main(skip_images=True)


@pytest.fixture(autouse=True)
def isolated_labels(tmp_path, monkeypatch):
    """Tests never write into the real review-label file (it is training data), the Remix approvals log or the imports."""
    monkeypatch.setattr(config, "LABELS_PATH", tmp_path / "review_labels.jsonl")
    monkeypatch.setattr(config, "REMIX_APPROVALS_PATH", tmp_path / "remix_approvals.jsonl")
    monkeypatch.setattr(config, "IMPORTS", tmp_path / "imports")      # nor into the real supplier-sheet imports
