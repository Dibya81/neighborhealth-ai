"""Alert message templates in English, Kannada and Hindi.
Kannada and Hindi text should be reviewed by native speakers before the pilot (Step 8 checklist)."""
from __future__ import annotations

BANDS = {
    "en": {"low": "low", "moderate": "moderate", "high": "high", "very_high": "very high"},
    "kn": {"low": "ಕಡಿಮೆ", "moderate": "ಮಧ್ಯಮ", "high": "ಹೆಚ್ಚು", "very_high": "ಅತಿ ಹೆಚ್ಚು"},
    "hi": {"low": "कम", "moderate": "मध्यम", "high": "उच्च", "very_high": "बहुत उच्च"},
}
PLACES = {
    "en": {"home": "home", "office": "office", "school": "school", "other": "saved place"},
    "kn": {"home": "ಮನೆ", "office": "ಕಚೇರಿ", "school": "ಶಾಲೆ", "other": "ಉಳಿಸಿದ ಸ್ಥಳ"},
    "hi": {"home": "घर", "office": "दफ़्तर", "school": "स्कूल", "other": "सहेजा गया स्थान"},
}
BODY = {
    "en": ("NeighborHealth alert: dengue risk around your {place} ({ward}) is {band} for the week ending {week}. "
           "This is an area estimate, not a diagnosis. This week: empty standing water in containers, coolers and tyres; "
           "use repellent and nets. Details: {link}"),
    "kn": ("NeighborHealth ಎಚ್ಚರಿಕೆ: ನಿಮ್ಮ {place} ({ward}) ಸುತ್ತಮುತ್ತ {week} ರಂದು ಮುಗಿಯುವ ವಾರದಲ್ಲಿ ಡೆಂಗ್ಯೂ ಅಪಾಯ {band} ಇದೆ. "
           "ಇದು ಪ್ರದೇಶದ ಅಂದಾಜು ಮಾತ್ರ, ರೋಗನಿರ್ಣಯವಲ್ಲ. ಈ ವಾರ: ಪಾತ್ರೆಗಳು, ಕೂಲರ್‌ಗಳು ಮತ್ತು ಟೈರ್‌ಗಳಲ್ಲಿ ನಿಂತ ನೀರನ್ನು ಖಾಲಿ ಮಾಡಿ; "
           "ಸೊಳ್ಳೆ ನಿವಾರಕ ಮತ್ತು ಸೊಳ್ಳೆ ಪರದೆ ಬಳಸಿ. ವಿವರಗಳು: {link}"),
    "hi": ("NeighborHealth सूचना: आपके {place} ({ward}) के आसपास {week} को समाप्त होने वाले सप्ताह में डेंगू का जोखिम {band} है। "
           "यह क्षेत्र का अनुमान है, निदान नहीं। इस सप्ताह: बर्तनों, कूलर और टायरों में जमा पानी खाली करें; "
           "मच्छर भगाने वाली क्रीम और मच्छरदानी का उपयोग करें। विवरण: {link}"),
}
SUBJECT = {
    "en": "Dengue risk is {band} around your {place}",
    "kn": "ನಿಮ್ಮ {place} ಸುತ್ತಮುತ್ತ ಡೆಂಗ್ಯೂ ಅಪಾಯ {band}",
    "hi": "आपके {place} के आसपास डेंगू का जोखिम {band}",
}


# How to opt out depends on the channel: email cannot be replied to, so it gets a one-click link.
FOOTER_STOP = {"en": "Reply STOP to unsubscribe.", "kn": "ನಿಲ್ಲಿಸಲು STOP ಎಂದು ಉತ್ತರಿಸಿ.", "hi": "बंद करने के लिए STOP लिखें।"}
FOOTER_LINK = {"en": "Unsubscribe: {unsub}", "kn": "ನಿಲ್ಲಿಸಲು: {unsub}", "hi": "बंद करने के लिए: {unsub}"}


def render(language: str, band: str, place: str, ward: str, week: str, link: str,
           channel: str = "sms", unsubscribe_link: str | None = None) -> tuple[str, str]:
    lang = language if language in BODY else "en"
    vals = {"band": BANDS[lang].get(band, band), "place": PLACES[lang].get(place, PLACES[lang]["other"]),
            "ward": ward, "week": week, "link": link}
    footer = (FOOTER_LINK[lang].format(unsub=unsubscribe_link) if channel == "email" and unsubscribe_link
              else FOOTER_STOP[lang])
    return SUBJECT[lang].format(**vals), BODY[lang].format(**vals) + "  " + footer
