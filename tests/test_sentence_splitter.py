from lecture_translator.translate.sentence_splitter import split_german


def test_simple():
    assert split_german("Hallo Welt. Wie geht es dir? Gut!") == [
        "Hallo Welt.",
        "Wie geht es dir?",
        "Gut!",
    ]


def test_abbreviations_do_not_split():
    s = split_german("Das ist z.B. ein Beispiel. Und das auch.")
    assert len(s) == 2
    assert s[0] == "Das ist z.B. ein Beispiel."


def test_bzw_abbrev():
    s = split_german("Die Regel gilt bzw. wird angewendet. Danach weiter.")
    assert len(s) == 2


def test_decimal_comma_at_sentence_end_splits():
    s = split_german("Der Wert beträgt 3,5. Weiter geht es.")
    assert s == ["Der Wert beträgt 3,5.", "Weiter geht es."]


def test_initials_do_not_split():
    s = split_german("Punkt A. Danach kommt Punkt B. Und Schluss.")
    assert s == ["Punkt A. Danach kommt Punkt B. Und Schluss."]


def test_ordinal_number_does_not_split():
    s = split_german("Kapitel 5. Einführung in die Physik.")
    assert s == ["Kapitel 5. Einführung in die Physik."]


def test_ellipsis_with_lowercase_continuation():
    s = split_german("Ich weiß nicht... vielleicht später.")
    assert s == ["Ich weiß nicht... vielleicht später."]


def test_quoted_sentence():
    s = split_german('Er sagte: "Das ist gut." Dann ging er.')
    assert s == ['Er sagte: "Das ist gut."', "Dann ging er."]


def test_exclamation_and_question_split():
    s = split_german("Wirklich! Ja? Genau.")
    assert s == ["Wirklich!", "Ja?", "Genau."]


def test_no_text_loss():
    text = "Z.B. etwas. Und noch ein Satz mit 3,5 Werten! Wirklich? Also ja."
    assert " ".join(split_german(text)) == " ".join(text.split())


def test_long_sentence_fallback():
    words = ["Wort"] * 100
    text = " ".join(words)
    s = split_german(text, max_words=80)
    assert len(s) == 2
    assert " ".join(s) == text


def test_empty_input():
    assert split_german("") == []
    assert split_german("   ") == []


def test_single_sentence_no_punct():
    assert split_german("einfach so") == ["einfach so"]
