"""The conversation document and its token form, with no ROM."""

from __future__ import annotations

import pytest

from tools.webfoot import conversations as cv


@pytest.mark.parametrize("text", [
    "Hello there.",
    "Two\nlines.{page}Then a page.",
    "{08:03}Red{08:00} and a brace {{ kept.",
    "#Bottom box.",
])
def test_the_token_form_round_trips(text):
    assert cv.decode(cv.encode(text)) == text


def test_the_token_form_names_the_units_the_game_reads():
    assert cv.encode("a\nb{page}c") == "a\x0ab\x0bc"
    assert cv.encode("{08:03}x") == "\x08\x03x"


@pytest.mark.parametrize("text", ["{zz}", "{08:}", "open { brace"])
def test_a_token_that_is_not_one_is_refused(text):
    with pytest.raises(cv.ConversationError):
        cv.encode(text)


def test_a_document_round_trips_through_its_file(tmp_path):
    document = cv.Document(
        lines={"0:0x0010:24": cv.Line("New words.", "Old words.")},
        talks={
            "talk-1": cv.Talk("First", ("Hello.", "#Bye."), (87, 0), 1, "met", "met", "talk-2"),
            "talk-2": cv.Talk("Later", ("Again.",), (112,)),
        },
        flags={"met": 157},
    )
    assert cv.read_document(tmp_path).is_empty()
    cv.write_document(tmp_path, document)
    assert cv.read_document(tmp_path) == document
    cv.write_document(tmp_path, cv.Document())
    assert cv.read_document(tmp_path).is_empty()


@pytest.mark.parametrize("body", [
    "[lines]\nnot-a-line = { text = 'a', was = 'b' }\n",
    "[talks.wrong]\nname = 'x'\n",
    "[talks.talk-1]\nname = 'x'\npages = 'one'\nportraits = [1]\n",
    "[flags]\n'Bad Name' = 157\n",
])
def test_a_document_that_cannot_be_trusted_is_refused(tmp_path, body):
    path = tmp_path / cv.CONVERSATIONS_FILE
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    with pytest.raises(cv.ConversationError):
        cv.read_document(tmp_path)
