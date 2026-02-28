from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


import pandas as pd
from pathlib import Path


# =================================================
# APP INIT
# =================================================

app = FastAPI(
    title="AYUSH–ICD-11 Terminology Microservice",
    description="NAMASTE → TM2 → ICD-11 (rule-based, full coverage, offline-ready)",
    version="1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # PoC ke liye OK
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =================================================
# PATH SETUP
# =================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

AYURVEDA_FILE = DATA_DIR / "NATIONAL AYURVEDA MORBIDITY CODES.xls"
SIDDHA_FILE   = DATA_DIR / "NATIONAL SIDDHA MORBIDITY CODES.xls"
UNANI_FILE    = DATA_DIR / "NATIONAL UNANI MORBIDITY CODES.xls"

# =================================================
# LOAD DATASETS
# =================================================

errors = {}

def load_excel(path: Path):
    try:
        df = pd.read_excel(path)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        errors[path.name] = str(e)
        return None

df_ayurveda = load_excel(AYURVEDA_FILE)
df_siddha   = load_excel(SIDDHA_FILE)
df_unani    = load_excel(UNANI_FILE)

# =================================================
# HEALTH CHECK
# =================================================

@app.get("/")
def health():
    return {
        "status": "running",
        "datasets_loaded": {
            "ayurveda": 0 if df_ayurveda is None else len(df_ayurveda),
            "siddha":   0 if df_siddha   is None else len(df_siddha),
            "unani":    0 if df_unani    is None else len(df_unani)
        },
        "errors": errors
    }

# =================================================
# SEARCH / AUTOCOMPLETE (VALUESET LOOKUP)
# =================================================

@app.get("/search")
def search(
    term: str = Query(..., min_length=2),
    system: str = Query("ayurveda", enum=["ayurveda", "siddha", "unani"])
):
    q = term.lower().strip()

    df = {
        "ayurveda": df_ayurveda,
        "siddha": df_siddha,
        "unani": df_unani
    }.get(system)

    if df is None:
        return {"status": "error", "message": f"{system} dataset not loaded"}

    text_cols = [
        c for c in df.columns
        if any(k in c.lower() for k in ["term", "word", "translation"])
    ]

    results = df[
        df[text_cols]
        .astype(str)
        .apply(lambda x: x.str.lower().str.contains(q, na=False))
        .any(axis=1)
    ].head(20)

    if results.empty:
        return {"status": "not_found", "query": term, "system": system}

    return {
        "status": "success",
        "count": len(results),
        "results": [
            {
                "system": system,
                "code": row.get("NAMC_CODE") or row.get("Code"),
                "term": row.get("NAMC_term") or row.get("Term") or row.get("Word")
            }
            for _, row in results.iterrows()
        ]
    }

# =================================================
# DOMAIN → TM2 → ICD-11 RULE ENGINE (FULL COVERAGE)
# =================================================

DOMAIN_RULES = [

    # Fever / infection
    {
        "keywords": ["fever", "jvara", "pyrexia", "humma", "taap"],
        "tm2": {"code": "TM2-FEB", "term": "Febrile disorders"},
        "icd11": {"code": "MG26", "term": "Fever, unspecified"}
    },

    # Digestive / GI
    {
        "keywords": [
            "digestion", "indigestion", "ajirna", "agnimandya",
            "grahani", "amlapitta", "gastritis", "diarrhea",
            "diarrhoea", "constipation", "stomach", "abdominal"
        ],
        "tm2": {"code": "TM2-GI", "term": "Gastrointestinal disorders"},
        "icd11": {"code": "DA64", "term": "Functional dyspepsia"}
    },

    # Respiratory
    {
        "keywords": [
            "cough", "kasa", "shwasa", "asthma",
            "breathing", "dyspnea", "bronchitis"
        ],
        "tm2": {"code": "TM2-RESP", "term": "Respiratory disorders"},
        "icd11": {"code": "CA23", "term": "Asthma"}
    },

    # Neurology
    {
        "keywords": [
            "migraine", "headache", "shiroroga",
            "ardhavabhedaka", "vertigo", "dizziness"
        ],
        "tm2": {"code": "TM2-NEURO", "term": "Neurological disorders"},
        "icd11": {"code": "8A80", "term": "Migraine"}
    },

    # Skin
    {
        "keywords": [
            "skin", "rash", "eczema", "psoriasis",
            "kushtha", "itching", "dermatitis"
        ],
        "tm2": {"code": "TM2-DERM", "term": "Dermatological disorders"},
        "icd11": {"code": "EA80", "term": "Dermatitis, unspecified"}
    },

    # Metabolic
    {
        "keywords": [
            "diabetes", "prameha", "madhumeha",
            "sugar", "blood sugar"
        ],
        "tm2": {"code": "TM2-MET", "term": "Metabolic disorders"},
        "icd11": {"code": "5A11", "term": "Type 2 diabetes mellitus"}
    },

    # Musculoskeletal
    {
        "keywords": [
            "joint pain", "arthritis", "sandhivata",
            "back pain", "neck pain", "muscle pain"
        ],
        "tm2": {"code": "TM2-MSK", "term": "Musculoskeletal disorders"},
        "icd11": {"code": "FA20", "term": "Osteoarthritis"}
    }
]

DEFAULT_TM2 = {
    "code": "TM2-GEN",
    "term": "General traditional medicine disorder"
}

DEFAULT_ICD11 = {
    "code": "ZZ00",
    "term": "Condition not elsewhere classified"
}

def infer_tm2_icd11(term: str):
    t = term.lower()
    for rule in DOMAIN_RULES:
        if any(k in t for k in rule["keywords"]):
            return rule["tm2"], rule["icd11"]
    return DEFAULT_TM2, DEFAULT_ICD11

# =================================================
# TRANSLATE (WORKS FOR ALL DISEASES)
# =================================================

@app.get("/translate")
def translate(
    system: str = Query(..., enum=["ayurveda", "siddha", "unani"]),
    term: str = Query(...)
):
    tm2, icd11 = infer_tm2_icd11(term)

    return {
        "resourceType": "Condition",
        "clinicalStatus": "active",
        "code": {
            "coding": [
                {
                    "system": f"NAMASTE-{system.upper()}",
                    "display": term,
                    "mappingType": "recorded"
                },
                {
                    "system": "ICD-11-TM2",
                    "code": tm2["code"],
                    "display": tm2["term"],
                    "mappingType": "rule-based"
                },
                {
                    "system": "ICD-11",
                    "code": icd11["code"],
                    "display": icd11["term"],
                    "mappingType": "suggested"
                }
            ]
        }
    }
# =================================================
# FHIR CodeSystem – NAMASTE Ayurveda (SAMPLE)
# =================================================

@app.get("/fhir/codesystem/ayurveda")
def fhir_codesystem_ayurveda():
    if df_ayurveda is None:
        return {"error": "Ayurveda dataset not loaded"}

    sample = df_ayurveda.head(3)

    concepts = []
    for _, row in sample.iterrows():
        concepts.append({
            "code": row.get("NAMC_CODE") or row.get("Code"),
            "display": row.get("NAMC_term") or row.get("Term") or row.get("Word")
        })

    return {
        "resourceType": "CodeSystem",
        "id": "namaste-ayurveda",
        "url": "https://ayush.gov.in/namaste/ayurveda",
        "name": "NAMASTE Ayurveda",
        "status": "active",
        "content": "example",
        "concept": concepts
    }
# =================================================
# FHIR ConceptMap – NAMASTE Ayurveda → TM2 / ICD-11 (SAMPLE)
# =================================================

@app.get("/fhir/conceptmap/ayurveda")
def fhir_conceptmap_ayurveda():
    return {
        "resourceType": "ConceptMap",
        "id": "namaste-ayurveda-to-icd11",
        "status": "active",
        "sourceUri": "https://ayush.gov.in/namaste/ayurveda",
        "targetUri": "https://icd.who.int/icd11",
        "group": [
            {
                "source": "NAMASTE-Ayurveda",
                "target": "ICD-11-TM2",
                "element": [
                    {
                        "code": "Ajirna",
                        "display": "Indigestion",
                        "target": [
                            {
                                "code": "TM2-GI",
                                "display": "Gastrointestinal disorders",
                                "equivalence": "relatedto"
                            }
                        ]
                    },
                    {
                        "code": "Jvara",
                        "display": "Fever",
                        "target": [
                            {
                                "code": "TM2-FEB",
                                "display": "Febrile disorders",
                                "equivalence": "relatedto"
                            }
                        ]
                    }
                ]
            },
            {
                "source": "NAMASTE-Ayurveda",
                "target": "ICD-11",
                "element": [
                    {
                        "code": "Ajirna",
                        "display": "Indigestion",
                        "target": [
                            {
                                "code": "DA64",
                                "display": "Functional dyspepsia",
                                "equivalence": "relatedto"
                            }
                        ]
                    },
                    {
                        "code": "Jvara",
                        "display": "Fever",
                        "target": [
                            {
                                "code": "MG26",
                                "display": "Fever, unspecified",
                                "equivalence": "relatedto"
                            }
                        ]
                    }
                ]
            }
        ]
    }
# =================================================
# FHIR Bundle Upload Endpoint (PoC)
# =================================================

from fastapi import Request

@app.post("/fhir/bundle")
async def upload_fhir_bundle(request: Request):
    bundle = await request.json()

    return {
        "status": "bundle received",
        "resourceType": bundle.get("resourceType", "Unknown")
    }
# =================================================
# FHIR Patient Resource (PoC)
# =================================================

from datetime import datetime
from fastapi import Body

@app.post("/fhir/patient")
def create_patient(patient: dict = Body(...)):
    fhir_patient = {
        "resourceType": "Patient",
        "id": "patient-001",
        "active": True,
        "name": [
            {
                "use": "official",
                "text": patient.get("name", "Unknown")
            }
        ],
        "gender": patient.get("gender", "unknown"),
        "birthDate": patient.get("birthDate", "2000-01-01"),
        "meta": {
            "lastUpdated": datetime.utcnow().isoformat()
        }
    }

    return fhir_patient

# =================================================
# FHIR Condition (Problem List) Resource
# =================================================

from datetime import datetime
from fastapi import Body

@app.post("/fhir/condition")
def create_condition(payload: dict = Body(...)):
    """
    Expected payload:
    {
      "patient_id": "patient-001",
      "system": "ayurveda",
      "term": "digestion"
    }
    """

    system = payload.get("system")
    term = payload.get("term")

    # Reuse existing translate logic
    tm2, icd11 = infer_tm2_icd11(term)

    condition = {
        "resourceType": "Condition",
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active"
                }
            ]
        },
        "subject": {
            "reference": f"Patient/{payload.get('patient_id')}"
        },
        "code": {
            "coding": [
                {
                    "system": f"NAMASTE-{system.upper()}",
                    "display": term
                },
                {
                    "system": "ICD-11-TM2",
                    "code": tm2["code"],
                    "display": tm2["term"]
                },
                {
                    "system": "ICD-11",
                    "code": icd11["code"],
                    "display": icd11["term"]
                }
            ]
        },
        "recordedDate": datetime.utcnow().isoformat()
    }

    return condition
# =================================================
# FHIR Report / Encounter Bundle (PoC)
# =================================================

from fastapi import Body
from datetime import datetime
import uuid

@app.post("/fhir/report")
def generate_fhir_report(payload: dict = Body(...)):
    """
    Expected payload:
    {
      "patient": { ...FHIR Patient JSON... },
      "condition": { ...FHIR Condition JSON... }
    }
    """

    bundle_id = str(uuid.uuid4())

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat(),
        "entry": [
            {
                "fullUrl": f"urn:uuid:{bundle_id}-patient",
                "resource": payload.get("patient")
            },
            {
                "fullUrl": f"urn:uuid:{bundle_id}-condition",
                "resource": payload.get("condition")
            }
        ]
    }

    return bundle
