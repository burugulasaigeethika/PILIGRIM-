"""
PilgrimAI - Telugu Script & Phonetic Query Normalizer

Pure Python, deterministic, offline preprocessor for pilgrimage queries in Telugu script.
Normalizes both native Telugu queries and Telugu-script phonetic English queries
into canonical temple entities and intent keywords prior to agent routing and RAG retrieval.

Zero model downloads, zero external API calls, zero mutations of RAG data.
"""

import re
from typing import Tuple, List, Dict

# Telugu Unicode range: \u0C00 - \u0C7F
TELUGU_SCRIPT_PATTERN = re.compile(r"[\u0C00-\u0C7F]")

# Canonical Temple Mappings (Telugu script -> Canonical English name)
# Ordered by descending length of key to ensure multi-word matches first
TELUGU_TEMPLE_MAPPINGS: List[Tuple[str, str]] = [
    ("వేయి స్తంభాల గుడి", "Thousand Pillar Temple"),
    ("చిలుకూరి బాలాజీ", "Chilkur Balaji"),
    ("కర్మన్ఘాట్ ధ్యానాంజనేయ", "Karmanghat Hanuman Temple"),
    ("కర్మన్‌ఘాట్ ధ్యానాంజనేయ", "Karmanghat Hanuman Temple"),
    ("కర్మన్‌ఘాట్", "Karmanghat Hanuman Temple"),
    ("కర్మన్ఘాట్", "Karmanghat Hanuman Temple"),
    ("నాచార గుట్ట", "Nacharam Gutta"),
    ("నాచారగుట్ట", "Nacharam Gutta"),
    ("యాదగిరిగుట్ట", "Yadadri"),
    ("యాదాద్రి", "Yadadri"),
    ("భద్రాచలం", "Bhadrachalam"),
    ("శ్రీశైలం", "Srisailam"),
    ("వేములవాడ", "Vemulawada"),
    ("బాసర", "Basara"),
    ("కొండగట్టు", "Kondagattu"),
    ("ధర్మపురి", "Dharmapuri"),
    ("ఏడుపాయల", "Edupayala"),
    ("కొలనుపాక", "Kolanupaka"),
    ("భద్రకాళి", "Bhadrakali Temple"),
    ("రామప్ప", "Ramappa Temple"),
    ("చిలుకూరు", "Chilkur Balaji"),
    ("బిర్లా మందిర్", "Birla Mandir"),
    ("బిర్లామందిర్", "Birla Mandir"),
    ("కీసరగుట్ట", "Keesaragutta"),
    ("జోగులాంబ", "Jogulamba Temple"),
    ("ఆలంపూర్", "Jogulamba Temple"),
    ("సురేంద్రపురి", "Surendrapuri"),
    ("కాళేశ్వరం", "Kaleshwaram"),
    ("హనుమకొండ", "Thousand Pillar Temple"),
    ("హైదరాబాద్", "Hyderabad"),
]

# Telugu Intent & Phrase Mappings (Multi-word phrases first, then single words)
TELUGU_INTENT_MAPPINGS: List[Tuple[str, str]] = [
    # Phonetic English phrases in Telugu script
    ("వాట్ ఆర్ ద", "what are the"),
    ("హౌ ఫార్ ఈజ్", "how far is"),
    ("హౌ ఫార్ ఇస్", "how far is"),
    ("హౌ టు రీచ్", "how to reach"),
    ("హౌ మచ్", "how much"),
    
    # Native Telugu intent phrases
    ("ఎలా చేరుకోవాలి", "how to reach"),
    ("దర్శన సమయాలు", "darshan timings"),
    ("ఆలయ సమయాలు", "temple timings"),
    ("ఆలయం", "temple"),
    ("గుడి", "temple"),
    ("ఆలయ", "temple"),

    # Phonetic English individual tokens in Telugu script
    ("టెంపుల్", "temple"),
    ("టైమింగ్స్", "timings"),
    ("టైమింగ్", "timings"),
    ("దర్శన్", "darshan"),
    ("రూమ్స్", "rooms"),
    ("రూమ్", "room"),
    ("లాడ్జింగ్", "lodging"),
    ("హోటల్స్", "hotels"),
    ("హోటల్", "hotel"),
    ("ఫెసిలిటీస్", "facilities"),
    ("ఫెసిలిటీ", "facility"),
    ("వెదర్", "weather"),
    ("బడ్జెట్", "budget"),
    ("టికెట్", "ticket"),
    ("టికెట్లు", "tickets"),
    ("రూట్", "route"),
    ("డిస్టెన్స్", "distance"),
    ("ఇన్ఫర్మేషన్", "information"),
    ("ఇన్ఫో", "information"),
    ("వాట్", "what"),
    ("ఆర్", "are"),
    ("ద", "the"),
    ("ఆఫ్", "of"),
    ("ఈజ్", "is"),
    ("ఇస్", "is"),
    ("ఫ్రమ్", "from"),
    ("టు", "to"),

    # Native Telugu keywords
    ("సమయాలు", "timings"),
    ("సమయం", "timings"),
    ("దర్శనం", "darshan"),
    ("సేవలు", "sevas"),
    ("సేవ", "sevas"),
    ("పూజలు", "poojas"),
    ("పూజ", "pooja"),
    ("వసతి", "accommodation"),
    ("ప్రసాదం", "prasadam"),
    ("సౌకర్యాలు", "facilities"),
    ("సౌకర్యం", "facilities"),
    ("దారి", "directions"),
    ("వాతావరణం", "weather"),
    ("చరిత్ర", "history"),
    ("వివరాలు", "information"),
    ("సమాచారం", "information"),
    ("ఖర్చు", "cost"),
    ("ధర", "cost"),
    ("ధరలు", "costs"),
    ("ఎంత", "how much"),
    ("ఎక్కడ", "where is"),
    ("ఏమిటి", "what is"),
    ("ఏంటి", "what is"),
]


def normalize_telugu_query(query: str) -> Tuple[str, bool]:
    """
    Normalizes a user query containing Telugu script into a canonical English representation.

    Args:
        query: The raw user query string.

    Returns:
        Tuple of (normalized_query_string, is_telugu_script_detected: bool).
        If no Telugu script is detected, returns (original_query, False).
    """
    if not query or not query.strip():
        return query, False

    is_telugu = bool(TELUGU_SCRIPT_PATTERN.search(query))
    if not is_telugu:
        return query, False

    text = query.strip()

    # Step 1: Detect and replace temple entities
    detected_temples = []
    for te_temple, canonical_name in TELUGU_TEMPLE_MAPPINGS:
        if te_temple in text:
            detected_temples.append(canonical_name)
            text = text.replace(te_temple, f" {canonical_name} ")

    # Step 2: Replace intent phrases and phonetic keywords
    for te_phrase, en_equiv in TELUGU_INTENT_MAPPINGS:
        if te_phrase in text:
            text = text.replace(te_phrase, f" {en_equiv} ")

    # Step 3: Clean up any remaining Telugu particles, question marks, and excess whitespace
    # Replace remaining Telugu script characters with space
    text = TELUGU_SCRIPT_PATTERN.sub(" ", text)

    # Normalize whitespace and punctuation
    text = re.sub(r"[?,.:;!]+", " ", text)
    tokens = [tok.strip() for tok in text.split() if tok.strip()]
    normalized = " ".join(tokens)

    # Step 4: Ensure semantic coherence for canonical routing
    # If temple was detected along with specific intents, construct a standard canonical query
    temple = detected_temples[0] if detected_temples else ""
    norm_lower = normalized.lower()

    if temple:
        if "timing" in norm_lower:
            return f"What are the temple timings of {temple}?", True
        elif "darshan" in norm_lower:
            return f"What are the darshan details for {temple}?", True
        elif "seva" in norm_lower or "pooja" in norm_lower:
            return f"What are the sevas and poojas at {temple}?", True
        elif "accommodation" in norm_lower or "room" in norm_lower or "lodging" in norm_lower:
            return f"What is the accommodation at {temple}?", True
        elif "prasadam" in norm_lower:
            return f"What is the prasadam at {temple}?", True
        elif "weather" in norm_lower:
            return f"What is the weather at {temple}?", True
        elif "cost" in norm_lower or "budget" in norm_lower or "ticket" in norm_lower:
            return f"What will a visit to {temple} cost?", True
        elif "reach" in norm_lower or "route" in norm_lower or "direction" in norm_lower or "distance" in norm_lower:
            return f"How to reach {temple}?", True
        elif "history" in norm_lower or "information" in norm_lower:
            return f"Give me the information about {temple} temple.", True
        elif not normalized or normalized.strip() == temple:
            return f"Give me information about {temple} temple.", True

    # If normalized has meaningful English tokens, return capitalized representation
    if normalized:
        return normalized.strip(), True

    return query, True
