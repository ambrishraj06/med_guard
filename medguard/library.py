"""
MedGuard — library.py
=====================
Built-in guideline library + question→source auto-matching (Level-1 automation).

Each entry is a SHORT, simplified educational summary of long-established public
health guidance (WHO/CDC/NICE-style), written so MedGuard has a measuring stick
for common questions without any retrieval infrastructure. They are NOT verbatim
quotes from official documents — real deployments should replace them with
licensed guideline chunks.

match_source(question) picks the most relevant entry by word overlap (with light
stemming and stopwords). Pure Python — zero new dependencies, fits any free host.
"""

from __future__ import annotations

import re

# Each entry: topic (short label), reference (provenance hint), text (the measuring stick)
LIBRARY: list[dict] = [
    {
        "topic": "UTI in pregnancy",
        "keywords": ["urine", "urinary", "uti", "bladder", "cystitis", "pregnant", "pregnancy"],
        "reference": "Public guidance summary (WHO/CDC/NICE-style) — educational, simplified",
        "text": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
    },
    {
        "topic": "Fever in children",
        "keywords": ["fever", "child", "kid", "temperature", "paracetamol", "viral", "virus"],
        "reference": "Public guidance summary (WHO/CDC/NICE-style) — educational, simplified",
        "text": (
            "Aspirin should not be given to children with viral infections because of the risk of "
            "Reye's syndrome. Paracetamol or ibuprofen are preferred alternatives for fever control "
            "in children, dosed by body weight."
        ),
    },
    {
        "topic": "Anaphylaxis emergency treatment",
        "keywords": ["allergic", "allergy", "reaction", "adrenaline", "epipen", "anaphylaxis", "treat", "treatment"],
        "reference": "Public guidance summary (WHO/NICE-style) — educational, simplified",
        "text": (
            "Intramuscular adrenaline (epinephrine) 1:1000 at a dose of 0.5 mg should be administered "
            "immediately into the anterolateral thigh for the treatment of anaphylaxis in adults. "
            "Antihistamines may be given afterwards for symptom relief but should never delay adrenaline."
        ),
    },
    {
        "topic": "High blood pressure lifestyle changes",
        "keywords": ["blood pressure", "salt", "exercise", "hypertension", "bp"],
        "reference": "Public guidance summary (WHO/ESC-style) — educational, simplified",
        "text": (
            "Adults with newly diagnosed hypertension should be advised to reduce salt intake to less "
            "than 5 g per day and to engage in at least 150 minutes of moderate-intensity aerobic "
            "exercise per week. Weight loss is recommended for patients who are overweight."
        ),
    },
    {
        "topic": "Vitamin C and the common cold",
        "keywords": ["vitamin", "cold", "colds", "supplement", "c"],
        "reference": "Public guidance summary — educational, simplified",
        "text": (
            "Regular vitamin C supplementation has not been shown to prevent the common cold in the "
            "general population, though it may slightly reduce the duration of symptoms."
        ),
    },
    {
        "topic": "Paracetamol safe dosing and overdose",
        "keywords": ["paracetamol", "overdose", "liver", "dose", "painkiller"],
        "reference": "Public guidance summary (FDA/MHRA-style) — educational, simplified",
        "text": (
            "For adults, the maximum daily dose of paracetamol is 4 g per day, taken as divided doses. "
            "In suspected paracetamol overdose, the patient must go to hospital immediately; an "
            "antidote called N-acetylcysteine can be given in hospital. Paracetamol overdose causes "
            "liver failure."
        ),
    },
    {
        "topic": "Type 2 diabetes first-line treatment",
        "keywords": ["diabetes", "sugar", "metformin", "diabetic"],
        "reference": "Public guidance summary (ADA/NICE-style) — educational, simplified",
        "text": (
            "For most adults with type 2 diabetes, metformin is the recommended first-line medicine, "
            "together with lifestyle changes including diet, exercise and weight reduction. Insulin "
            "may be added later if blood sugar remains uncontrolled."
        ),
    },
    {
        "topic": "Antibiotics do not work on viruses",
        "keywords": ["antibiotic", "antibiotics", "virus", "viral", "bacteria", "resistance", "cold", "flu"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "Antibiotics are not effective against viral infections such as the common cold, flu, or "
            "most sore throats. Taking antibiotics when they are not needed causes side effects and "
            "drives antibiotic resistance."
        ),
    },
    {
        "topic": "MMR vaccine and autism",
        "keywords": ["mmr", "vaccine", "autism", "measles", "jab", "immunization", "immunisation"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "The MMR (measles, mumps, rubella) vaccine is safe and effective. Large studies across "
            "millions of children show no link between the MMR vaccine and autism."
        ),
    },
    {
        "topic": "Iron deficiency anaemia",
        "keywords": ["iron", "anaemia", "anemia", "tired", "haemoglobin", "hemoglobin"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Iron deficiency anaemia is treated with oral iron supplements, usually taken once daily "
            "or on alternate days. Vitamin C can improve iron absorption, while tea and coffee reduce "
            "it. A cause for the iron loss should always be identified."
        ),
    },
    {
        "topic": "Asthma inhalers",
        "keywords": ["asthma", "inhaler", "salbutamol", "wheeze", "breathing", "puffer"],
        "reference": "Public guidance summary (GINA/NICE-style) — educational, simplified",
        "text": (
            "People with asthma use a reliever inhaler (such as salbutamol) for sudden symptoms and a "
            "daily preventer inhaler (inhaled corticosteroid) to control inflammation. Using the "
            "reliever inhaler more than three times a week is a sign that asthma is not well controlled."
        ),
    },
    {
        "topic": "Penicillin allergy",
        "keywords": ["penicillin", "allergy", "allergic", "cephalosporin", "antibiotic"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Patients with a confirmed penicillin allergy should avoid penicillin antibiotics. "
            "Cross-reactivity with cephalosporins is low but not zero, so choice depends on the "
            "severity of the previous reaction."
        ),
    },
    {
        "topic": "Diarrhoea and dehydration",
        "keywords": ["diarrhoea", "diarrhea", "dehydration", "ors", "rehydration", "stool", "loose motion"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "For diarrhoea, the priority is preventing dehydration with oral rehydration solution "
            "(ORS), sipped continuously. Seek medical care if there is blood in the stool, high "
            "fever, or signs of severe dehydration."
        ),
    },
    {
        "topic": "Smoking cessation",
        "keywords": ["smoking", "smoke", "quit", "cigarette", "vaping", "tobacco"],
        "reference": "Public guidance summary (NICE/CDC-style) — educational, simplified",
        "text": (
            "The most effective way to stop smoking combines behavioural support with medicines such "
            "as nicotine replacement therapy or varenicline. Quitting smoking reduces the risk of "
            "heart disease, stroke, and cancer at any age."
        ),
    },
]

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "for", "in", "on", "at",
    "to", "and", "or", "with", "without", "what", "how", "can", "could", "should", "would",
    "will", "do", "does", "did", "i", "my", "me", "we", "you", "your", "they", "them", "it",
    "its", "from", "by", "as", "that", "this", "these", "those", "there", "if", "when", "have",
    "has", "had", "not", "no", "yes", "about", "into", "out", "up", "down", "any", "some",
    "take", "taking", "using", "use", "give", "given", "tell", "much", "many", "more", "most",
    "also", "get", "got",
}

_IRREGULAR = {"children": "child", "women": "woman", "men": "man", "feet": "foot"}


def _stem(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _words(text: str) -> set:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return {
        _stem(w)
        for w in raw
        if w not in _STOPWORDS and len(w) > 2
    }


def match_source(question: str, min_score: int = 2) -> tuple[dict | None, int]:
    """Return (best_library_entry, score) for a question, or (None, 0) if nothing
    clears the threshold.

    Score = word overlap between question and chunk (stemmed, stopwords removed)
           + 2 points per keyword hit (keywords capture how real users phrase a topic).
    """
    q_lower = question.lower()
    q_words = _words(question)
    if not q_words:
        return None, 0
    best, best_score = None, 0
    for entry in LIBRARY:
        chunk_words = _words(entry["topic"] + " " + entry["text"])
        score = len(q_words & chunk_words)
        for kw in entry.get("keywords", []):
            if " " in kw:
                if kw in q_lower:
                    score += 2
            elif _stem(kw) in q_words:
                score += 2
        if score > best_score:
            best, best_score = entry, score
    if best is None or best_score < min_score:
        return None, 0
    return best, best_score
