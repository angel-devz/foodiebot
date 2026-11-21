"""Intent classifier: TF-IDF (word + character n-grams) + Logistic Regression.

Character n-grams make the model tolerant to typos ("shiping", "refnd"),
word n-grams capture phrases ("track order", "cash on delivery").
"""
import json
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from .nlp import normalize

ROOT = Path(__file__).resolve().parent.parent
INTENTS_PATH = ROOT / "data" / "intents.json"
MODEL_PATH = ROOT / "model" / "intent_model.joblib"


def load_intents(path: Path = INTENTS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def training_data(intents: dict) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for intent in intents["intents"]:
        for pattern in intent["patterns"]:
            texts.append(normalize(pattern))
            labels.append(intent["tag"])
    return texts, labels


def build_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
    ])
    clf = LogisticRegression(C=20, max_iter=5000, class_weight="balanced")
    return Pipeline([("features", features), ("clf", clf)])


def train(intents: dict) -> Pipeline:
    texts, labels = training_data(intents)
    pipeline = build_pipeline()
    pipeline.fit(texts, labels)
    return pipeline


def save(pipeline: Pipeline, path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)


def load_or_train(path: Path = MODEL_PATH, intents_path: Path = INTENTS_PATH) -> Pipeline:
    """Load the saved model; retrain if it is missing or older than intents.json."""
    if path.exists() and path.stat().st_mtime >= intents_path.stat().st_mtime:
        return joblib.load(path)
    pipeline = train(load_intents(intents_path))
    save(pipeline, path)
    return pipeline
