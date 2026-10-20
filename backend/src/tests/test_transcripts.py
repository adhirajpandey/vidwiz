from src import transcripts


def test_quote_covers_ten_seconds_before_and_five_after():
    transcript = [
        {"text": "thirty seconds ago", "offset": 70, "duration": 4},
        {"text": "outside before", "offset": 85, "duration": 4},
        {"text": "ten seconds before", "offset": 90, "duration": 2},
        {"text": "at capture", "offset": 100, "duration": 2},
        {"text": "five seconds after", "offset": 105, "duration": 2},
        {"text": "outside after", "offset": 106, "duration": 2},
    ]
    assert transcripts.quote_for(transcript, 100) == (
        "ten seconds before at capture five seconds after",
        90,
    )


def test_quote_caps_dense_speech_and_keeps_the_end():
    text = "earlier words " * 40 + "the final thought"
    quote, start = transcripts.quote_for([{"text": text, "offset": 100}], 100)
    assert len(quote) <= 350
    assert quote.startswith("…")
    assert quote.endswith("the final thought")
    assert start == 100


def test_saved_passage_keeps_its_separate_character_limit():
    text = "word " * 400
    assert (
        len(transcripts.text_between([{"text": text, "offset": 100}], 90, 110)) == 1400
    )
