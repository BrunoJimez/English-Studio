import pytest
from app.scoring import compare, excerpt


def test_punctuation_and_contractions():
    assert compare("I'm ready. We can't wait!", "I am ready we cannot wait")["score"] == 100


def test_substitution_deletion_insertion():
    r = compare("we will watch the film", "we can watch film tomorrow")
    assert r["errors"] == 3
    assert r["score"] == 40
    assert sum(w["kind"] != "correct" for w in r["alignment"]) == 3


def test_empty_and_excessive_answer():
    assert compare("hello", "")["score"] == 0
    assert compare("hello", "hello one two three")["score"] == 0
    with pytest.raises(ValueError):
        compare("...", "hello")


def test_repeated_word_alignment():
    result = compare("I think I can", "I think think I can")
    assert result["errors"] == 1
    assert result["score"] == 75
    assert [w["kind"] for w in result["alignment"]].count("extra") == 1


def test_exact_clip_word_boundaries():
    segments = [{"start": 1, "end": 5, "text": "Hello world today", "words": [
        {"start": 1, "end": 2, "word": " Hello"}, {"start": 2, "end": 3, "word": " world"},
        {"start": 4, "end": 5, "word": " today"}]}]
    assert excerpt(segments, 2, 4) == "world"
    assert excerpt(segments, 5, 6) == ""
    assert excerpt(segments, 1.5, 2.5) == "Hello"


def test_edited_segment_is_used_whole():
    assert excerpt([{"start": 2, "end": 4, "text": "A corrected reference.", "words": []}], 3, 5) == "A corrected reference."
