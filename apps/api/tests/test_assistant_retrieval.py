"""Retrieval gate tests against the real indexed guidelines (skipped if the index has not been built)."""
import pytest

from app.services.assistant.assistant import select_passages
from app.services.assistant.corpus import is_noise, stem
from app.services.assistant.retrieval import _index

pytestmark = pytest.mark.skipif(_index() is None, reason="run `make guidelines` to build the guideline index")


@pytest.mark.parametrize("q", ["What is the capital of France?", "Explain quantum computing.",
                               "Which hospital in Bengaluru is best for dengue?", "Who won the cricket world cup?"])
def test_out_of_scope_questions_are_refused(q):
    assert select_passages(q, k=3) == []


def test_aspirin_question_finds_the_avoid_guidance():
    top = select_passages("Can I take aspirin or ibuprofen for dengue?", k=3)
    assert any("acetylsalicylic" in p["text"].lower() or "aspirin" in p["text"].lower() or "nsaid" in p["text"].lower()
               for p in top)


def test_every_returned_passage_comes_from_an_official_source():
    for p in select_passages("How can I prevent mosquito breeding?", k=5):
        assert p["org"] and p["url"] and p["page"]


def test_front_matter_and_reference_lists_are_never_indexed():
    assert is_noise("The mention of specific companies does not imply that they are endorsed by the WHO.")
    assert is_noise("1. Smith J. Dengue. Lancet 2001. 2. Lee K. J Infect 1999. 3. Roy A. BMJ 2010. 4. Das B. 2005.")
    assert not is_noise("Give oral fluids and paracetamol. Avoid aspirin. Watch for warning signs.")


def test_stemmer_keeps_words_that_only_look_like_plurals():
    assert stem("symptoms") == "symptom" and stem("getting") == "get"
    assert stem("dangerous") == "dangerous" and stem("virus") == "virus"
