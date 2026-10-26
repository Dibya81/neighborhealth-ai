"""Export every Kannada/Hindi string the API can send to a person, next to the English, for native-speaker review.

    cd apps/api && PYTHONPATH=../..:. python scripts/export_translations.py > ../../docs/v2/TRANSLATION_REVIEW.md
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../..")

from app.services.alerts import templates as t  # noqa: E402
from app.services.assistant import assistant as a  # noqa: E402


def rows(name: str, table: dict) -> list[tuple[str, str, str, str]]:
    out = []
    for key in (table["en"] if isinstance(table["en"], dict) else [None]):
        get = (lambda lang: table[lang][key]) if key is not None else (lambda lang: table[lang])
        out.append((name + (f" / {key}" if key else ""), get("en"), get("kn"), get("hi")))
    return out


def main() -> None:
    items = []
    for name, table in [("Alert subject", t.SUBJECT), ("Alert body", t.BODY), ("Risk band", t.BANDS),
                        ("Place label", t.PLACES), ("Opt-out (SMS/WhatsApp)", t.FOOTER_STOP),
                        ("Opt-out (email link)", t.FOOTER_LINK), ("URGENT: warning signs", a.URGENT),
                        ("Assistant: cannot diagnose", a.NO_DIAGNOSIS), ("Assistant: not in sources", a.NOT_FOUND)]:
        items += rows(name, table)
    print("# Kannada and Hindi review sheet\n")
    print("Please check each Kannada (kn) and Hindi (hi) line against the English: correct meaning, natural wording,\n"
          "respectful tone, and nothing that sounds like a diagnosis. **The URGENT row matters most**: it is shown to\n"
          "someone who may be seriously ill. Placeholders like `{band}`, `{ward}`, `{link}` must stay as they are.\n")
    print("Reviewer name: ____________  Date: ________  Verdict: [ ] approved  [ ] changes needed\n")
    for name, en, kn, hi in items:
        print(f"## {name}\n- **en:** {en}\n- **kn:** {kn}\n- **hi:** {hi}\n- Reviewer comment (kn): \n- Reviewer comment (hi): \n")
    print("## Also review: warning-sign keywords (assistant)\n"
          "These words trigger the urgent message. Add missing common ways to say them, and remove any that\n"
          "would fire on harmless sentences.\n\n- " + "\n- ".join(a.WARNING_SIGNS))


if __name__ == "__main__":
    main()
