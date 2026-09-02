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
        "source_name": "CDC / NICE",
        "keywords": ["urine", "urinary", "uti", "bladder", "cystitis", "wee", "peeing", "burning", "pregnant", "pregnancy"],
        "reference": "Public guidance summary (WHO/CDC/NICE-style) — educational, simplified",
        "text": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
    },
    {
        "topic": "Fever in children",
        "source_name": "WHO / NICE",
        "keywords": ["fever", "feverish", "child", "kid", "toddler", "baby", "temperature", "hot"],
        "reference": "Public guidance summary (WHO/CDC/NICE-style) — educational, simplified",
        "text": (
            "Aspirin should not be given to children with viral infections because of the risk of "
            "Reye's syndrome. Paracetamol or ibuprofen are preferred alternatives for fever control "
            "in children, dosed by body weight."
        ),
    },
    {
        "topic": "Anaphylaxis emergency treatment",
        "source_name": "WHO / Resuscitation Council-style",
        "keywords": ["anaphylaxis", "adrenaline", "epipen", "epipen", "throat closing", "swelling", "emergency", "shock"],
        "reference": "Public guidance summary (WHO/NICE-style) — educational, simplified",
        "text": (
            "Intramuscular adrenaline (epinephrine) 1:1000 at a dose of 0.5 mg should be administered "
            "immediately into the anterolateral thigh for the treatment of anaphylaxis in adults. "
            "Antihistamines may be given afterwards for symptom relief but should never delay adrenaline."
        ),
    },
    {
        "topic": "High blood pressure lifestyle changes",
        "source_name": "NICE / WHO",
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
        "source_name": "Public health guidance summary",
        "keywords": ["vitamin", "cold", "colds", "supplement", "c"],
        "reference": "Public guidance summary — educational, simplified",
        "text": (
            "Regular vitamin C supplementation has not been shown to prevent the common cold in the "
            "general population, though it may slightly reduce the duration of symptoms."
        ),
    },
    {
        "topic": "Paracetamol safe dosing and overdose",
        "source_name": "FDA / MHRA-style",
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
        "source_name": "ADA / NICE",
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
        "source_name": "WHO / CDC",
        "keywords": ["antibiotic", "antibiotics", "virus", "viral", "bacteria", "sore throat", "flu", "sinus"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "Antibiotics are not effective against viral infections such as the common cold, flu, or "
            "most sore throats. Taking antibiotics when they are not needed causes side effects and "
            "drives antibiotic resistance."
        ),
    },
    {
        "topic": "MMR vaccine and autism",
        "source_name": "WHO / CDC",
        "keywords": ["mmr", "vaccine", "autism", "measles", "jab", "immunization", "immunisation"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "The MMR (measles, mumps, rubella) vaccine is safe and effective. Large studies across "
            "millions of children show no link between the MMR vaccine and autism."
        ),
    },
    {
        "topic": "Iron deficiency anaemia",
        "source_name": "NICE",
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
        "source_name": "GINA / NICE",
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
        "source_name": "NICE",
        "keywords": ["penicillin", "amoxicillin", "cephalosporin", "rash", "reaction to antibiotic", "penicillin allergy", "allergic to penicillin"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Patients with a confirmed penicillin allergy should avoid penicillin antibiotics. "
            "Cross-reactivity with cephalosporins is low but not zero, so choice depends on the "
            "severity of the previous reaction."
        ),
    },
    {
        "topic": "Diarrhoea and dehydration",
        "source_name": "WHO",
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
        "source_name": "NICE / CDC",
        "keywords": ["smoking", "smoke", "quit", "cigarette", "vaping", "tobacco"],
        "reference": "Public guidance summary (NICE/CDC-style) — educational, simplified",
        "text": (
            "The most effective way to stop smoking combines behavioural support with medicines such "
            "as nicotine replacement therapy or varenicline. Quitting smoking reduces the risk of "
            "heart disease, stroke, and cancer at any age."
        ),
    },
    {
        "topic": "Dengue fever",
        "source_name": "WHO / ICMR",
        "keywords": ["dengue", "dengue fever", "breakbone", "platelet", "haemorrhagic", "hemorrhagic", "mosquito"],
        "reference": "Public guidance summary (WHO/ICMR-style) — educational, simplified",
        "text": (
            "Dengue is a mosquito-borne viral infection. There is no specific antiviral medicine; "
            "treatment is supportive — rest, plenty of fluids, and paracetamol for fever and pain. "
            "NSAIDs such as aspirin or ibuprofen must be avoided because they increase the risk of "
            "bleeding. Go to hospital immediately if warning signs appear: severe abdominal pain, "
            "persistent vomiting, bleeding from gums or nose, blood in vomit or stool, or extreme "
            "tiredness and restlessness."
        ),
    },
    {
        "topic": "Malaria",
        "source_name": "WHO",
        "keywords": ["malaria", "artemisinin", "rdt", "parasite", "plasmodium", "mosquito"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Malaria should be confirmed by a blood test (microscopy or a rapid diagnostic test) "
            "before starting treatment. Uncomplicated malaria is treated with artemisinin-based "
            "combination therapy (ACT). Severe malaria is a medical emergency treated with "
            "injectable artesunate in hospital. Prevention relies on avoiding mosquito bites, "
            "especially sleeping under insecticide-treated bed nets."
        ),
    },
    {
        "topic": "Tuberculosis (TB)",
        "source_name": "WHO",
        "keywords": ["tuberculosis", "tb", "cough", "sputum", "isoniazid", "rifampicin", "mdr", "lung"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Active tuberculosis is treated with a combination of antibiotics for at least 6 months — "
            "commonly isoniazid, rifampicin, pyrazinamide, and ethambutol for 2 months, then "
            "isoniazid and rifampicin for 4 months. The full course must be completed exactly as "
            "prescribed; stopping early can cause relapse and drug-resistant TB. A cough lasting "
            "more than 2 weeks, or coughing up blood, should be tested for TB."
        ),
    },
    {
        "topic": "HIV treatment and prevention",
        "source_name": "WHO",
        "keywords": ["hiv", "aids", "antiretroviral", "art", "undetectable", "prep", "virus"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "HIV is diagnosed with a blood test. There is no cure, but lifelong antiretroviral "
            "therapy (ART) — a daily combination of medicines — controls the virus and lets people "
            "live long, healthy lives. People taking effective ART who reach an undetectable viral "
            "load do not pass HIV on through sex. Condoms and pre-exposure prophylaxis (PrEP) "
            "prevent sexual transmission."
        ),
    },
    {
        "topic": "Healthy pregnancy basics",
        "source_name": "WHO",
        "keywords": ["pregnancy", "pregnant", "folic", "vitamin", "antenatal", "breastfeeding", "trimester", "baby", "conceive", "miscarriage"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Women planning pregnancy should take a daily folic acid supplement (400 micrograms) "
            "before conception and during the first 12 weeks to prevent neural tube defects. WHO "
            "recommends at least 8 antenatal care visits during pregnancy. Alcohol and smoking harm "
            "the unborn baby and should be avoided completely. Exclusive breastfeeding is "
            "recommended for the first 6 months."
        ),
    },
    {
        "topic": "Antibiotic stewardship",
        "source_name": "WHO",
        "keywords": ["stewardship", "resistance", "resistant", "course", "leftover", "prescribed", "finish", "skip", "dose"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Antibiotics must be taken exactly as prescribed, and the full course must be completed "
            "even if you feel better. Never take leftover antibiotics or antibiotics prescribed for "
            "someone else. Misuse of antibiotics — taking them when not needed, skipping doses, or "
            "stopping early — drives antimicrobial resistance, which makes infections harder to "
            "treat in everyone."
        ),
    },
    {
        "topic": "High cholesterol",
        "source_name": "NICE",
        "keywords": ["cholesterol", "statin", "atorvastatin", "ldl", "lipid", "cardiovascular"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "High cholesterol is treated first with lifestyle changes — reducing saturated fat, "
            "eating more fibre, exercising regularly, and stopping smoking. For people at high "
            "cardiovascular risk, statins such as atorvastatin are the first-line medicines to "
            "lower LDL cholesterol. Statins are usually taken for life; severe muscle pain while "
            "on a statin should be reported to a doctor."
        ),
    },
    {
        "topic": "Depression treatment",
        "source_name": "NICE",
        "keywords": ["depression", "depressed", "antidepressant", "ssri", "mental", "mood", "sad"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "For mild depression, the first treatments are guided self-help, regular exercise, and "
            "talking therapies such as cognitive behavioural therapy (CBT). For moderate to severe "
            "depression, antidepressant medicines (SSRIs) may be prescribed. Antidepressants take "
            "2 to 4 weeks to start working, should be taken every day, and must never be stopped "
            "suddenly."
        ),
    },
    {
        "topic": "Low blood sugar (hypoglycaemia)",
        "source_name": "NICE / ADA",
        "keywords": ["hypoglycemia", "hypoglycaemia", "low blood sugar", "insulin", "glucose", "shaking", "diabetic emergency"],
        "reference": "Public guidance summary (NICE/ADA-style) — educational, simplified",
        "text": (
            "Low blood sugar (sweating, shaking, confusion, feeling faint) in a person with diabetes "
            "is treated immediately with 15–20 g of fast-acting sugar — glucose tablets or a small "
            "glass of juice — then rechecked after 15 minutes. If the person becomes unconscious, "
            "nothing must be given by mouth; call emergency services immediately."
        ),
    },
    {
        "topic": "Heart attack first aid",
        "source_name": "NHS / AHA-style",
        "keywords": ["heart attack", "chest pain", "cardiac", "aspirin", "emergency", "heart"],
        "reference": "Public guidance summary (NHS/AHA-style) — educational, simplified",
        "text": (
            "A suspected heart attack — chest pain or pressure, possibly spreading to the arm, "
            "neck, or jaw, with sweating, nausea, or shortness of breath — is a medical emergency: "
            "call emergency services immediately. While waiting, the person should sit down and "
            "rest. Chewing a single 300 mg aspirin is recommended unless the person is allergic "
            "to aspirin or has been told not to take it."
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

    Scoring (tuned to avoid topic confusion):
      + 1  per content word shared with the topic/chunk text (stemmed, stopwords removed)
      + 2  per single-word keyword hit (how real users phrase a topic)
      + 4  per multi-word phrase keyword hit (e.g. "chest pain", "penicillin allergy") —
           these are the most distinctive signals, so they dominate generic word overlap.
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
                    score += 4
            elif _stem(kw) in q_words:
                score += 2
        if score > best_score:
            best, best_score = entry, score
    if best is None or best_score < min_score:
        return None, 0
    return best, best_score
