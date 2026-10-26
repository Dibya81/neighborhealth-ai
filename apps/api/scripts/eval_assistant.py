"""Evaluate the assistant's retrieval against questions with known answers.

    cd apps/api && PYTHONPATH=../..:. python scripts/eval_assistant.py

Each answerable question lists regexes that must ALL appear inside one of the top-3 passages
(i.e. the passage really contains the answer). Out-of-scope questions must be refused. This does not
need an LLM key: it measures whether the right official text is found, which is what the citations
depend on. Citation accuracy of LLM-written answers is checked separately (verified after generation).
"""
from __future__ import annotations

import json
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../..")

from app.services.assistant.assistant import select_passages  # noqa: E402

ANSWERABLE = [
    ("What are the symptoms of dengue?", [r"headache", r"(muscle|joint)"]),
    ("How is dengue spread?", [r"(bite|transmitted|transmission).{0,80}mosquito|mosquito.{0,80}(bite|transmit)"]),
    ("How can I prevent mosquito breeding at home?", [r"(cover|lid|empty|drain|dry)", r"(water|container|tank)"]),
    ("At what time of day does the Aedes mosquito bite?", [r"(early morning|dusk|daytime|day time|day-time|morning)", r"aedes|mosquito"]),
    ("How long after a mosquito bite do dengue symptoms start?", [r"(incubation|[3-9].{0,8}(7|10|14) days|5.{0,3}6 days)"]),
    ("What are the warning signs of severe dengue?", [r"warning", r"(abdominal pain|persistent vomiting|mucosal bleed|lethargy|restless)"]),
    ("Which blood test confirms dengue?", [r"(NS1|IgM|ELISA|PCR)", r"(confirm|diagnos)"]),
    ("What is the NS1 antigen test?", [r"NS1", r"(early|viraemi|viremi|first)"]),
    ("Is there a vaccine for dengue?", [r"vaccine", r"dengue"]),
    ("Can I take aspirin or ibuprofen for dengue?", [r"(acetylsalicylic|aspirin|NSAID|ibuprofen)"]),
    ("What is fogging?", [r"fogging", r"(adult|kill)"]),
    ("How much fluid should a dengue patient take?", [r"(oral fluid|fluids|ml/kg|ORS)", r"(dengue|patient)"]),
    ("What does a low platelet count mean in dengue?", [r"platelet"]),
    ("What is dengue shock syndrome?", [r"shock", r"(dengue shock syndrome|DSS)"]),
    ("Where does the Aedes mosquito lay eggs?", [r"eggs?", r"(water|container)"]),
    ("Can dengue spread directly from one person to another?", [r"(person.to.person|directly|human to human|not spread)"]),
    ("Which medicine can I take for fever in dengue?", [r"paracetamol"]),
    ("In which places do Aedes mosquitoes breed?", [r"(tyres?|coolers?|flower pots?|overhead tank|containers?|discarded)"]),
    ("How long does dengue fever last?", [r"(2.{0,4}7 days|1.{0,4}2 weeks|7 days)"]),
    ("How far can the Aedes mosquito fly?", [r"100 ?m|flight range|metres|meters"]),
    ("What is dengue haemorrhagic fever?", [r"(haemorrhagic|hemorrhagic)", r"(DHF|fever)"]),
    ("What should I drink if I have dengue?", [r"(fluids|ORS|coconut|juice|rice water|oral)"]),
    ("Who is at higher risk of severe dengue?", [r"(infants|elderly|pregnan|second infection|secondary|previous|comorbid|diabet)"]),
    ("What is the treatment for dengue?", [r"(supportive|symptomatic|no specific|antiviral)"]),
    ("What is the role of the community in preventing dengue?", [r"(communit|COMBI|neighbourhood|households?)"]),
    ("What is the Aedes mosquito life cycle?", [r"(egg).{0,60}(larva)|larva.{0,60}pupa"]),
]
OUT_OF_SCOPE = [
    "What is the capital of France?",
    "Which hospital in Bengaluru is best for dengue?",
    "How do I treat cancer?",
    "What is the price of a smartphone?",
    "Who won the cricket world cup?",
]


def main() -> None:
    hit = 0
    misses = []
    for q, pats in ANSWERABLE:
        top = select_passages(q, k=3)
        ok = any(all(re.search(p, c["text"], re.I | re.S) for p in pats) for c in top)
        hit += ok
        if not ok:
            misses.append((q, [(c["source_id"], c["page"], round(c["score"], 1)) for c in top]))
    refused = 0
    wrongly_answered = []
    for q in OUT_OF_SCOPE:
        top = select_passages(q, k=3)
        if not top:
            refused += 1
        else:
            wrongly_answered.append((q, [(c["source_id"], c["page"], round(c["score"], 1)) for c in top]))
    res = {"answerable": len(ANSWERABLE), "recall_at_3": round(hit / len(ANSWERABLE), 3),
           "out_of_scope": len(OUT_OF_SCOPE), "correctly_refused": refused,
           "missed": misses, "wrongly_answered": wrongly_answered}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
