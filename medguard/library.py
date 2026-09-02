"""
MedGuard — library.py
=====================
Comprehensive built-in medical guideline library + question→source auto-matching.

66 topics: common diseases, emergencies, chronic conditions, medicines, first aid
and umbrella public-health topics (WHO / CDC / NICE / ICMR / AHA / GOLD / ATA style).

IMPORTANT HONESTY NOTE: each entry is a SHORT, simplified educational summary of
long-established public guidance — NOT verbatim quotes from official documents.
The named source indicates which organisation's public guidance the summary follows.
Real deployments should swap in licensed verbatim guideline chunks.

match_source(question) scores by keyword hits (multi-word phrases weigh 4x —
they are the most distinctive signals) plus stemmed word overlap, with medical
stopwords removed. Umbrella topics (medicines, pain, vaccines, diet, first aid)
catch broad health questions; truly off-topic questions still score 0 → the
app honestly abstains (CAN'T CHECK) instead of guessing.
"""

from __future__ import annotations

import re

# Each entry: topic, source_name (what the UI cites), keywords (how users ask),
# reference (provenance note), text (the measuring stick).
LIBRARY: list[dict] = [
    # ------------------------------------------------------------------ infections
    {
        "topic": "UTI in pregnancy",
        "source_name": "CDC / NICE",
        "keywords": ["urine", "urinary", "uti", "bladder", "cystitis", "wee", "peeing", "burning pee", "burns when i pee", "stinging pee", "pregnant", "pregnancy"],
        "reference": "Public guidance summary (CDC/NICE-style) — educational, simplified",
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
        "reference": "Public guidance summary (WHO/NICE-style) — educational, simplified",
        "text": (
            "Aspirin should not be given to children with viral infections because of the risk of "
            "Reye's syndrome. Paracetamol or ibuprofen are preferred alternatives for fever control "
            "in children, dosed by body weight."
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
        "keywords": ["tuberculosis", "tb cough", "sputum", "isoniazid", "rifampicin", "mdr", "night sweat", "coughing blood"],
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
        "keywords": ["hiv", "aids", "antiretroviral", "art", "undetectable", "prep"],
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
        "topic": "COVID-19",
        "source_name": "WHO",
        "keywords": ["covid", "covid-19", "coronavirus", "sars-cov-2", "pandemic"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Most COVID-19 illness is mild and treated at home with rest, fluids, and paracetamol "
            "for fever. Antibiotics do not treat COVID-19 because it is a viral infection. "
            "Vaccination sharply reduces the risk of severe disease and hospitalisation. Seek "
            "emergency care for difficulty breathing, persistent chest pain, or confusion."
        ),
    },
    {
        "topic": "Influenza (flu)",
        "source_name": "WHO / CDC",
        "keywords": ["flu", "influenza", "oseltamivir", "tamiflu"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "Influenza is a viral infection that usually gets better on its own with rest and "
            "fluids; paracetamol relieves fever and aches. Antibiotics do not treat flu. For "
            "people at high risk, antiviral medicines such as oseltamivir work best when started "
            "within 48 hours of symptoms. Annual flu vaccination is recommended for high-risk groups."
        ),
    },
    {
        "topic": "Pneumonia",
        "source_name": "WHO / CDC",
        "keywords": ["pneumonia", "chest infection", "sputum", "lung infection"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "Pneumonia is often bacterial and is treated with antibiotics chosen by a doctor after "
            "assessment — the full course must be completed. Seek emergency care for fast breathing, "
            "chest pain, blue lips, or confusion. Pneumococcal and flu vaccination reduces risk in "
            "older adults and high-risk groups."
        ),
    },
    {
        "topic": "Hepatitis B",
        "source_name": "WHO",
        "keywords": ["hepatitis", "hepatitis b", "hbsag", "jaundice", "liver infection"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Hepatitis B spreads through blood and sexual contact and is vaccine-preventable. "
            "Most adults clear the infection themselves; chronic infection is monitored and treated "
            "with antiviral medicines by a liver specialist. People with hepatitis B should avoid "
            "alcohol and have regular liver checks."
        ),
    },
    {
        "topic": "Sexually transmitted infections",
        "source_name": "WHO / CDC",
        "keywords": ["sti", "std", "sexually transmitted", "chlamydia", "gonorrhea", "gonorrhoea", "condom"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "Many sexually transmitted infections are curable with prescribed antibiotics, but "
            "self-treatment is dangerous — testing first is essential because symptoms overlap. "
            "Condoms prevent transmission, and partners should be tested and treated together. "
            "Untreated STIs can cause infertility."
        ),
    },
    {
        "topic": "Food poisoning",
        "source_name": "WHO",
        "keywords": ["food poisoning", "vomiting", "thrown up", "ate bad", "food poisoning", "gastroenteritis"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Food poisoning usually settles by itself; the priority is fluids with oral "
            "rehydration solution. Antibiotics are usually not needed. See a doctor for blood in "
            "the stool, high fever, symptoms lasting more than 3 days, or signs of dehydration."
        ),
    },
    {
        "topic": "Rabies",
        "source_name": "WHO",
        "keywords": ["rabies", "dog bite", "animal bite", "bat bite", "monkey bite"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "After any animal bite that could carry rabies, wash the wound thoroughly with soap "
            "and running water for at least 15 minutes and get the rabies vaccine immediately — "
            "rabies is virtually always fatal once symptoms begin, so post-exposure vaccination is "
            "an emergency, never optional."
        ),
    },
    {
        "topic": "Snakebite",
        "source_name": "WHO",
        "keywords": ["snake", "snakebite", "snake bite", "viper", "cobra", "anti-venom", "antivenom"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "For snakebite, keep the person calm and still with the bitten limb immobilised and "
            "lower than the heart, and get to hospital immediately for anti-venom. Do NOT apply a "
            "tourniquet, cut the wound, suck out the venom, or apply ice — these outdated measures "
            "cause more harm."
        ),
    },
    {
        "topic": "Tetanus",
        "source_name": "WHO",
        "keywords": ["tetanus", "lockjaw", "rusty nail", "dirty wound", "booster"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Tetanus is prevented by vaccination; a dirty or deep wound in anyone not fully "
            "vaccinated needs a booster dose. Clean all wounds thoroughly. Jaw stiffness or muscle "
            "spasms after a wound are an emergency — tetanus has no cure, only prevention."
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
        "topic": "MMR vaccine and autism",
        "source_name": "WHO / CDC",
        "keywords": ["mmr", "vaccine autism", "measles", "jab", "immunization", "immunisation"],
        "reference": "Public guidance summary (WHO/CDC-style) — educational, simplified",
        "text": (
            "The MMR (measles, mumps, rubella) vaccine is safe and effective. Large studies across "
            "millions of children show no link between the MMR vaccine and autism."
        ),
    },
    # ------------------------------------------------------------------ chronic
    {
        "topic": "Type 2 diabetes first-line treatment",
        "source_name": "ADA / NICE",
        "keywords": ["diabetes", "sugar", "metformin", "diabetic", "hba1c"],
        "reference": "Public guidance summary (ADA/NICE-style) — educational, simplified",
        "text": (
            "For most adults with type 2 diabetes, metformin is the recommended first-line medicine, "
            "together with lifestyle changes including diet, exercise and weight reduction. Insulin "
            "may be added later if blood sugar remains uncontrolled."
        ),
    },
    {
        "topic": "High blood pressure lifestyle changes",
        "source_name": "NICE / WHO",
        "keywords": ["blood pressure", "hypertension", "bp", "salt", "exercise"],
        "reference": "Public guidance summary (NICE/WHO-style) — educational, simplified",
        "text": (
            "Adults with newly diagnosed hypertension should be advised to reduce salt intake to less "
            "than 5 g per day and to engage in at least 150 minutes of moderate-intensity aerobic "
            "exercise per week. Weight loss is recommended for patients who are overweight."
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
        "topic": "Stroke (FAST)",
        "source_name": "NICE / AHA-style",
        "keywords": ["stroke", "fast test", "face droop", "slurred speech", "paralysis", "brain attack"],
        "reference": "Public guidance summary (NICE/AHA-style) — educational, simplified",
        "text": (
            "A stroke is a medical emergency — call emergency services at the first sign of the "
            "FAST signs: Face drooping, Arm weakness, Speech difficulty, Time to call. Do not give "
            "the person food, drink, or medicines by mouth, and do not wait to see if it passes — "
            "every minute of delay damages more brain."
        ),
    },
    {
        "topic": "Chronic kidney disease",
        "source_name": "NICE / KDIGO-style",
        "keywords": ["kidney", "creatinine", "ckd", "dialysis", "renal", "kidney failure"],
        "reference": "Public guidance summary (NICE/KDIGO-style) — educational, simplified",
        "text": (
            "Chronic kidney disease is slowed by controlling blood pressure and blood sugar, "
            "avoiding long-term NSAID painkillers, staying hydrated, and having regular kidney "
            "function checks. It usually causes no symptoms until late, so blood and urine tests "
            "are how it is found."
        ),
    },
    {
        "topic": "Thyroid disorders",
        "source_name": "NICE / ATA-style",
        "keywords": ["thyroid", "hypothyroidism", "hyperthyroidism", "levothyroxine", "tsh", "thyroxine", "goitre"],
        "reference": "Public guidance summary (NICE/ATA-style) — educational, simplified",
        "text": (
            "An underactive thyroid (hypothyroidism) is treated with a daily levothyroxine tablet, "
            "taken on an empty stomach, usually for life, with regular TSH blood checks. An "
            "overactive thyroid is treated with antithyroid medicines, radioiodine, or surgery — "
            "it must never be self-managed."
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
        "topic": "COPD",
        "source_name": "GOLD / NICE-style",
        "keywords": ["copd", "emphysema", "smoker cough", "bronchitis"],
        "reference": "Public guidance summary (GOLD/NICE-style) — educational, simplified",
        "text": (
            "The single most important treatment for COPD is stopping smoking — the disease slows "
            "sharply after quitting. Inhalers that open the airways (bronchodilators) control "
            "symptoms, yearly flu and pneumococcal vaccines reduce flare-ups, and pulmonary "
            "rehabilitation improves breathing and quality of life."
        ),
    },
    {
        "topic": "Epilepsy and seizures",
        "source_name": "NICE",
        "keywords": ["epilepsy", "seizure", "fit", "convulsion", "antiepileptic", "keppra"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Epilepsy is usually controlled with daily antiepileptic medicines which must never be "
            "stopped suddenly. During a seizure: protect the head, do NOT restrain the person or "
            "put anything in their mouth, and after the jerking stops roll them onto their side. "
            "Call an ambulance if a seizure lasts more than 5 minutes or repeats without recovery."
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
        "topic": "Insomnia and sleep problems",
        "source_name": "NICE",
        "keywords": ["insomnia", "sleep", "cant sleep", "sleeping pill", "sleep hygiene"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "The first treatment for insomnia is sleep hygiene: a fixed wake-up time, no caffeine "
            "or screens late in the evening, and no daytime naps. Talking therapy (CBT for "
            "insomnia) is the recommended long-term treatment. Sleeping tablets are for short-term "
            "use only under a doctor's supervision because they cause dependence."
        ),
    },
    {
        "topic": "Migraine and headache",
        "source_name": "NICE",
        "keywords": ["migraine", "headache", "aura", "triptan", "head pain"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Migraine attacks are treated early in a dark, quiet room with simple painkillers or "
            "triptan medicines, and prevented by identifying triggers and keeping regular sleep and "
            "meals. A sudden, worst-ever headache, or headache with fever, stiff neck, or confusion "
            "is an emergency, not a migraine."
        ),
    },
    {
        "topic": "Gout",
        "source_name": "NICE / ACR-style",
        "keywords": ["gout", "urate", "uric acid", "big toe", "allopurinol", "colchicine"],
        "reference": "Public guidance summary (NICE/ACR-style) — educational, simplified",
        "text": (
            "An acute gout attack is treated with NSAIDs or colchicine (dose-adjusted for kidney "
            "problems). Long-term daily allopurinol lowers uric acid and prevents attacks but is "
            "never started during a flare. Limiting alcohol, red meat, and sugary drinks reduces "
            "attacks."
        ),
    },
    {
        "topic": "Joint pain and osteoarthritis",
        "source_name": "NICE",
        "keywords": ["arthritis", "osteoarthritis", "joint pain", "knee pain", "joints", "wear and tear"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "For osteoarthritis, strengthening exercise and weight loss are the core treatments — "
            "they reduce pain better than medicines. Paracetamol or short courses of NSAIDs help "
            "pain; long-term strong painkillers are discouraged. Joint replacement is a last "
            "resort for severe cases."
        ),
    },
    {
        "topic": "Back pain",
        "source_name": "NICE",
        "keywords": ["back pain", "backache", "spine", "lower back", "slipped disc"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "For ordinary back pain, keep active, use heat, and take short courses of NSAIDs — "
            "bed rest makes it worse. Red flags needing urgent medical review: leg weakness or "
            "numbness, loss of bladder or bowel control, fever, or pain after major injury."
        ),
    },
    {
        "topic": "Osteoporosis",
        "source_name": "NICE",
        "keywords": ["osteoporosis", "bone density", "fragile bones", "bisphosphonate", "calcium"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Osteoporosis is prevented and treated with calcium and vitamin D, regular "
            "weight-bearing exercise, and fall-proofing the home. For people at high fracture risk, "
            "bisphosphonate medicines slow bone loss. Smoking and long-term alcohol weaken bones."
        ),
    },
    {
        "topic": "Obesity and healthy weight",
        "source_name": "NICE",
        "keywords": ["obesity", "weight loss", "overweight", "bmi", "lose weight", "diet plan"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "The foundation of healthy weight loss is a modest calorie reduction with support — "
            "aiming for 5–10% weight loss, sustained. Medicines and surgery are options for higher "
            "BMAs but only under specialist care. Crash diets usually lead to regaining the weight."
        ),
    },
    {
        "topic": "Alcohol misuse",
        "source_name": "NICE / WHO",
        "keywords": ["alcohol", "drinking", "liquor", "hangover", "addiction", "withdrawal"],
        "reference": "Public guidance summary (NICE/WHO-style) — educational, simplified",
        "text": (
            "The safest alcohol advice is to keep well below national limits and have several "
            "alcohol-free days weekly. Sudden stopping after heavy long-term drinking causes "
            "dangerous withdrawal (shakes, seizures) and must be done with medical support. "
            "Confidential support services are effective and should be offered early."
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
        "topic": "Sickle cell disease",
        "source_name": "WHO",
        "keywords": ["sickle cell", "sickle", "hemoglobinopathy", "pain crisis", "vaso-occlusive"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Sickle cell disease is inherited; a pain crisis is treated with fluids, warmth, and "
            "medical-grade pain relief — a severe crisis is an emergency. Childhood vaccination "
            "plus daily penicillin prevents the infections that sickle cell patients are "
            "especially vulnerable to."
        ),
    },
    {
        "topic": "Thalassemia",
        "source_name": "WHO / ICMR",
        "keywords": ["thalassemia", "thalassaemia", "blood transfusion", "chelation", "genetic counseling"],
        "reference": "Public guidance summary (WHO/ICMR-style) — educational, simplified",
        "text": (
            "Thalassemia major needs lifelong regular blood transfusions plus chelation medicine to "
            "remove the excess iron transfusions deposit in the body. Genetic counselling before "
            "pregnancy is recommended for carrier couples, as it is an inherited condition."
        ),
    },
    {
        "topic": "Polycystic ovary syndrome",
        "source_name": "NICE",
        "keywords": ["pcos", "polycystic", "irregular period", "hirsutism", "ovary cyst"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "PCOS is managed first with weight control and exercise, which restore regular cycles "
            "in many. Hormonal medicines regulate periods and treat symptoms; metformin may help "
            "with insulin resistance. Persistently irregular periods should always be assessed."
        ),
    },
    # ------------------------------------------------------------------ medicines
    {
        "topic": "Paracetamol safe dosing and overdose",
        "source_name": "FDA / MHRA-style",
        "keywords": ["paracetamol", "overdose", "liver", "dose", "painkiller", "acetaminophen"],
        "reference": "Public guidance summary (FDA/MHRA-style) — educational, simplified",
        "text": (
            "For adults, the maximum daily dose of paracetamol is 4 g per day, taken as divided doses. "
            "In suspected paracetamol overdose, the patient must go to hospital immediately; an "
            "antidote called N-acetylcysteine can be given in hospital. Paracetamol overdose causes "
            "liver failure."
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
        "topic": "Anaphylaxis emergency treatment",
        "source_name": "WHO / Resuscitation Council-style",
        "keywords": ["anaphylaxis", "adrenaline", "epipen", "epipen", "throat closing", "swelling", "shock"],
        "reference": "Public guidance summary (WHO/Resuscitation-style) — educational, simplified",
        "text": (
            "Intramuscular adrenaline (epinephrine) 1:1000 at a dose of 0.5 mg should be administered "
            "immediately into the anterolateral thigh for the treatment of anaphylaxis in adults. "
            "Antihistamines may be given afterwards for symptom relief but should never delay adrenaline."
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
        "keywords": ["heart attack", "chest pain", "cardiac", "aspirin", "heart"],
        "reference": "Public guidance summary (NHS/AHA-style) — educational, simplified",
        "text": (
            "A suspected heart attack — chest pain or pressure, possibly spreading to the arm, "
            "neck, or jaw, with sweating, nausea, or shortness of breath — is a medical emergency: "
            "call emergency services immediately. While waiting, the person should sit down and "
            "rest. Chewing a single 300 mg aspirin is recommended unless the person is allergic "
            "to aspirin or has been told not to take it."
        ),
    },
    {
        "topic": "Warfarin and drug interactions",
        "source_name": "NICE",
        "keywords": ["warfarin", "blood thinner", "anticoagulant", "inr", "bleeding risk", "clotting"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Warfarin is a blood-thinning medicine with many dangerous interactions. Fluconazole, "
            "metronidazole, and NSAIDs such as ibuprofen must not be combined with warfarin — the "
            "combination causes a severe bleeding risk and is contraindicated. Patients on warfarin "
            "must have regular INR blood tests and check every new medicine with their doctor or "
            "pharmacist first."
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
        "topic": "Vitamin C and the common cold",
        "source_name": "Public health guidance summary",
        "keywords": ["vitamin c", "common cold", "cold prevention", "supplement"],
        "reference": "Public guidance summary — educational, simplified",
        "text": (
            "Regular vitamin C supplementation has not been shown to prevent the common cold in the "
            "general population, though it may slightly reduce the duration of symptoms."
        ),
    },
    # ------------------------------------------------------------------ skin / eyes / dental / GI
    {
        "topic": "Eczema (atopic dermatitis)",
        "source_name": "NICE",
        "keywords": ["eczema", "atopic", "dermatitis", "itchy skin", "rash"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Eczema is treated with daily fragrance-free moisturisers applied generously, plus "
            "topical steroid creams for flares, used in the strength and duration a doctor advises. "
            "Known triggers (soaps, detergents, certain fabrics) should be avoided. Sudden weeping, "
            "crusted, or painful skin may mean infection and needs medical review."
        ),
    },
    {
        "topic": "Psoriasis",
        "source_name": "NICE",
        "keywords": ["psoriasis", "silvery scales", "plaques", "skin flakes"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Psoriasis is a long-term immune condition, not contagious and not caused by poor "
            "hygiene. Mild cases are treated with topical steroid or vitamin-D-based creams; "
            "severe cases with phototherapy or systemic medicines under specialist care. Sudden "
            "widespread flares should be medically reviewed."
        ),
    },
    {
        "topic": "Acne",
        "source_name": "NICE / AAD-style",
        "keywords": ["acne", "pimples", "spots", "blackheads", "zit"],
        "reference": "Public guidance summary (NICE/AAD-style) — educational, simplified",
        "text": (
            "Acne is treated with gentle washing and topical treatments such as benzoyl peroxide or "
            "retinoids; moderate-to-severe acne needs prescription medicines such as oral "
            "antibiotics. Scrubbing hard and picking worsens scarring. Chocolate and poor hygiene "
            "are not the cause."
        ),
    },
    {
        "topic": "Scabies",
        "source_name": "WHO",
        "keywords": ["scabies", "itch at night", "burrows", "mite"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Scabies is treated with permethrin cream applied to the whole body, repeated after a "
            "week — and all household contacts should be treated together. Bedding and clothes "
            "should be washed hot. Intense night-time itching can continue for weeks after "
            "successful treatment."
        ),
    },
    {
        "topic": "Cataract",
        "source_name": "NICE",
        "keywords": ["cataract", "cloudy vision", "eye surgery", "lens"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "A cataract is a clouding of the eye's lens; the only effective treatment is day-case "
            "surgery to replace the lens, which is safe and highly successful. There is no eye drop "
            "or medicine that dissolves cataracts. Stronger glasses help in the early stages."
        ),
    },
    {
        "topic": "Glaucoma",
        "source_name": "NICE",
        "keywords": ["glaucoma", "eye pressure", "vision loss", "iop"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Glaucoma is raised eye pressure that silently damages vision — lost sight cannot be "
            "restored. It is treated with daily pressure-lowering eye drops, usually lifelong, and "
            "regular eye checks. Adults over 40 with a family history should have routine eye "
            "pressure tests."
        ),
    },
    {
        "topic": "Dental care and toothache",
        "source_name": "WHO / ADA-style",
        "keywords": ["toothache", "tooth", "dental", "cavity", "filling", "gum"],
        "reference": "Public guidance summary (WHO/ADA-style) — educational, simplified",
        "text": (
            "Tooth decay is prevented by brushing twice daily with fluoride toothpaste and limiting "
            "sugary food and drinks. Cavities need professional fillings — they never heal by "
            "themselves. Severe toothache, facial swelling, or fever from a tooth is a dental "
            "emergency needing prompt treatment."
        ),
    },
    {
        "topic": "Ear infection",
        "source_name": "NICE / AAP-style",
        "keywords": ["ear infection", "earache", "otitis media", "ear pain"],
        "reference": "Public guidance summary (NICE/AAP-style) — educational, simplified",
        "text": (
            "Most childhood ear infections are viral and settle in 2–3 days with paracetamol for "
            "pain — antibiotics are reserved for the under-2s or severe cases, chosen by a doctor. "
            "Cotton buds must never be pushed into ears. High fever, swelling behind the ear, or "
            "discharge needs medical review."
        ),
    },
    {
        "topic": "Stomach ulcer and H. pylori",
        "source_name": "NICE / ACG-style",
        "keywords": ["ulcer", "h pylori", "helicobacter", "stomach burn", "gastric", "acidity"],
        "reference": "Public guidance summary (NICE/ACG-style) — educational, simplified",
        "text": (
            "Stomach ulcers are usually caused by H. pylori infection or NSAID painkillers. "
            "H. pylori is confirmed by a test and cured with a short combination-antibiotic course; "
            "long-term NSAIDs should be avoided. Vomiting blood or black, tarry stools is an "
            "emergency — bleeding ulcer."
        ),
    },
    {
        "topic": "Constipation",
        "source_name": "NICE",
        "keywords": ["constipation", "constipated", "cant poop", "bowel movement", "laxative"],
        "reference": "Public guidance summary (NICE-style) — educational, simplified",
        "text": (
            "Constipation is treated first with more fibre, fluids, and movement; short courses of "
            "laxatives are safe when needed. A sudden change in bowel habit, blood in the stool, "
            "or unexplained weight loss is a red flag needing medical review."
        ),
    },
    # ------------------------------------------------------------------ first aid
    {
        "topic": "Burns first aid",
        "source_name": "NHS / Red Cross-style",
        "keywords": ["burn", "burnt", "scald", "boiling water", "hot pan"],
        "reference": "Public guidance summary (NHS/Red Cross-style) — educational, simplified",
        "text": (
            "Immediately cool a burn under gently running cool water for 10–20 minutes — never use "
            "ice, butter, or toothpaste. Remove jewellery near the burn and cover loosely with "
            "cling film. Burns larger than the person's palm, or on the face, hands, or joints, "
            "need emergency care."
        ),
    },
    {
        "topic": "Severe bleeding first aid",
        "source_name": "Red Cross-style",
        "keywords": ["bleeding", "cut", "wound", "blood loss", "haemorrhage", "hemorrhage"],
        "reference": "Public guidance summary (Red Cross-style) — educational, simplified",
        "text": (
            "For severe bleeding, press firmly on the wound with a clean cloth and keep pressing "
            "without lifting, raise the injured limb above heart level where possible, and call "
            "emergency services. Never remove a soaked dressing — add layers on top."
        ),
    },
    {
        "topic": "Poisoning first aid",
        "source_name": "WHO / Poisons Centre-style",
        "keywords": ["poison", "poisoning", "swallowed", "drank chemical", "overdose pills"],
        "reference": "Public guidance summary (WHO/Poisons-Centre-style) — educational, simplified",
        "text": (
            "If someone swallows a poisonous substance, do NOT make them vomit — call emergency "
            "services or the poisons centre immediately, and keep the container or a photo of the "
            "substance to tell medics exactly what was taken. Vomiting causes further damage on the "
            "way back up."
        ),
    },
    {
        "topic": "Fractures and sprains",
        "source_name": "NHS / Red Cross-style",
        "keywords": ["fracture", "broken bone", "sprain", "twisted ankle", "broken arm"],
        "reference": "Public guidance summary (NHS/Red Cross-style) — educational, simplified",
        "text": (
            "For a suspected fracture, keep the limb still, apply cold packs for swelling, and get "
            "medical care — never try to straighten or 'set' it. For sprains, the first 48 hours "
            "is rest, ice, compression, elevation. Numbness, deformity, or inability to bear weight "
            "means an X-ray is needed."
        ),
    },
    # ------------------------------------------------------------------ umbrellas
    {
        "topic": "Medicine safety essentials",
        "generic": True,
        "source_name": "WHO",
        "keywords": ["medicine safety", "two medicines", "mix medicines", "combine medicines", "medicines together", "miss a dose", "double dose", "shared medicine", "expired", "interactions"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Take every medicine exactly as prescribed — right dose, right time, full course. "
            "Never share prescription medicines or take someone else's, never stop a prescribed "
            "course early without asking a doctor, and check with a doctor or pharmacist before "
            "combining any medicines, supplements, or herbal products, because interactions can be "
            "dangerous."
        ),
    },
    {
        "topic": "Safe pain relief",
        "generic": True,
        "source_name": "WHO",
        "keywords": ["painkiller", "pain relief", "pain medicine", "analgesic", "paracetamol or ibuprofen", "ache relief"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "For ordinary pain, paracetamol (max 4 g/day for adults) or short courses of ibuprofen "
            "with food are the standard first choices, following pack doses exactly. Never combine "
            "multiple products that contain the same ingredient. Severe, sudden, or unexplained "
            "pain needs medical review rather than stronger painkillers."
        ),
    },
    {
        "topic": "Vaccination basics",
        "generic": True,
        "source_name": "WHO",
        "keywords": ["vaccine", "vaccines", "vaccination", "immunisation", "immunization", "jab", "booster"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "Vaccines are among the safest and most effective medical tools; routine immunisation "
            "protects against measles, polio, tetanus, hepatitis B and more, following the national "
            "schedule. Mild fever or sore arm afterwards is normal and settles. Skipping or delaying "
            "vaccines raises the risk of outbreaks."
        ),
    },
    {
        "topic": "Healthy diet and physical activity",
        "generic": True,
        "source_name": "WHO",
        "keywords": ["healthy eating", "diet", "nutrition", "fruit and vegetable", "balanced diet", "food groups", "calories"],
        "reference": "Public guidance summary (WHO-style) — educational, simplified",
        "text": (
            "WHO advises at least 400 g of fruit and vegetables daily, under 5 g of salt, under 10% "
            "of calories from free sugars, and 150–300 minutes of moderate activity weekly, plus "
            "limiting alcohol and not smoking. Fad and crash diets are discouraged — steady habits "
            "beat quick fixes."
        ),
    },
    {
        "topic": "When to seek emergency care",
        "generic": True,
        "source_name": "NHS / Red Cross-style",
        "keywords": ["ambulance", "emergency", "a&e", "er visit", "when to call", "urgent care", "999", "911"],
        "reference": "Public guidance summary (NHS/Red Cross-style) — educational, simplified",
        "text": (
            "Call emergency services immediately for: difficulty breathing, chest pain, signs of "
            "stroke (face droop, arm weakness, speech trouble), heavy bleeding, seizures that do not "
            "stop, unconsciousness, severe burns, or suspected poisoning. While waiting, keep the "
            "person safe and still, and do not give food or drink to anyone who may need surgery."
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


def match_source(question: str, min_keyword_hits: int = 1) -> tuple[dict | None, int]:
    """Return (best_library_entry, score) for a question, or (None, 0).

    Two-part rule (keeps unknown diseases honestly unmatched):
      1. A topic qualifies ONLY if the question hits at least one of its KEYWORDS
         — the words real users actually use for that topic. Generic word overlap
         alone (e.g. "medicine", "disease", "treatment" matching everything)
         never qualifies a topic. This is what makes unknown-disease questions
         abstain instead of landing on a random neighbor.
      2. Among qualifying topics, the highest score wins:
           +1 per content word shared with topic/chunk (stemmed, stopwords removed)
           +2 per single-word keyword hit
           +4 per multi-word phrase keyword hit (most distinctive signal)
    Umbrella entries (medicines, pain, vaccines, diet, emergencies) are marked
    generic=True and require TWO keyword hits to qualify — one generic word like
    "medicine" must never pull a whole question onto an umbrella topic.
    """
    q_lower = question.lower()
    q_words = _words(question)
    if not q_words:
        return None, 0
    best, best_score = None, 0
    for entry in LIBRARY:
        chunk_words = _words(entry["topic"] + " " + entry["text"])
        overlap = len(q_words & chunk_words)
        kw_score = 0
        kw_hits = 0
        for kw in entry.get("keywords", []):
            if " " in kw:
                if kw in q_lower:
                    kw_score += 4
                    kw_hits += 1
            elif _stem(kw) in q_words:
                kw_score += 2
                kw_hits += 1
        required = 2 if entry.get("generic") else 1
        if kw_hits < required:
            continue  # not a topic the user is actually asking about
        score = overlap + kw_score
        if score > best_score:
            best, best_score = entry, score
    if best is None:
        return None, 0
    return best, best_score
