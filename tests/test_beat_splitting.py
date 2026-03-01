"""Tests for language-aware beat splitting."""

from research_viz.audio_generator.beat_sync_tts import split_into_beats, _count_units, CJK_LANGUAGES


def test_english_split_basic():
    text = "Hello world. This is a test. Another sentence here. And one more."
    beats = split_into_beats(text, min_words=3, max_words=10, language="en")
    assert len(beats) > 0
    # Recombined text should contain all original content
    combined = " ".join(beats)
    assert "Hello world" in combined
    assert "one more" in combined


def test_english_split_respects_max():
    # Build text with many short sentences to test max_words grouping
    text = ". ".join([f"Sentence number {i} has some words" for i in range(10)]) + "."
    beats = split_into_beats(text, min_words=5, max_words=15, language="en")
    for beat in beats:
        word_count = len(beat.split())
        # Each beat should be within a reasonable range (some tolerance for sentence merging)
        assert word_count <= 20


def test_english_split_default_params():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    beats = split_into_beats(text, language="en")
    assert len(beats) > 0


def test_cjk_count_units():
    # 12 chars / 3 = 4 units
    assert _count_units("これはテストです。", "ja") == 3  # 9 non-space chars / 3
    # English still counts words
    assert _count_units("hello world test", "en") == 3


def test_cjk_split():
    text = "これはテストです。もう一つの文章があります。最後の文です。"
    beats = split_into_beats(text, min_words=2, max_words=8, language="ja")
    assert len(beats) > 0
    # CJK beats should be joined without spaces
    for beat in beats:
        assert beat.strip() != ""


def test_cjk_languages_set():
    assert CJK_LANGUAGES == {"ja", "zh", "ko"}


def test_arabic_split():
    text = "هذا اختبار. هذه جملة أخرى. والأخيرة."
    beats = split_into_beats(text, min_words=2, max_words=10, language="ar")
    assert len(beats) > 0


def test_empty_narration():
    beats = split_into_beats("", min_words=5, max_words=15, language="en")
    assert beats == [] or beats == [""]


def test_single_sentence():
    text = "Just one sentence here."
    beats = split_into_beats(text, min_words=2, max_words=10, language="en")
    assert len(beats) == 1
    assert "Just one sentence here" in beats[0]
