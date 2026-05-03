from squire.corpus import file_corpus


def test_file_corpus_concatenates_with_xml_tags(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha")
    b.write_text("beta")

    corpus, used, total = file_corpus([a, b], max_input_chars=1000)

    assert "<file path=" in corpus
    assert "alpha" in corpus and "beta" in corpus
    assert used == [str(a), str(b)]
    assert total == len("alpha") + len("beta")


def test_file_corpus_truncates_when_budget_exhausted(tmp_path):
    big = tmp_path / "big.txt"
    big.write_text("x" * 10000)

    corpus, used, total = file_corpus([big], max_input_chars=500)

    assert "[TRUNCATED BY squire max_input_chars]" in corpus
    # 500 chars kept + the truncation marker length is also counted in `total`
    assert 500 <= total < 1000
    # exactly 500 consecutive x's were taken from the file
    assert "x" * 500 in corpus
    assert "x" * 501 not in corpus
    assert used == [str(big)]


def test_file_corpus_stops_when_budget_runs_out(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("Z" * 100)
    b.write_text("Q" * 100)

    corpus, used, total = file_corpus([a, b], max_input_chars=100)

    # First file exactly fills budget; second file shouldn't appear.
    assert str(a) in used
    assert str(b) not in used
    assert "Z" * 100 in corpus
    assert "Q" not in corpus


def test_file_corpus_empty_paths_returns_empty(tmp_path):
    corpus, used, total = file_corpus([], max_input_chars=1000)
    assert corpus == ""
    assert used == []
    assert total == 0
