"""Train the intent model and report its accuracy.

Usage:  python train.py
"""
import json
import time

from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score

from chatbot.model import MODEL_PATH, ROOT, build_pipeline, load_intents, save, train, training_data
from chatbot.nlp import normalize


def main() -> None:
    intents = load_intents()
    texts, labels = training_data(intents)
    print(f"Intents: {len(intents['intents'])} | training patterns: {len(texts)}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(build_pipeline(), texts, labels, cv=cv)
    print(f"5-fold cross-validation accuracy: {scores.mean():.1%} (+/- {scores.std():.1%})")

    start = time.perf_counter()
    model = train(intents)
    print(f"Trained in {time.perf_counter() - start:.2f}s")
    save(model)
    print(f"Saved model -> {MODEL_PATH.relative_to(ROOT)}")

    with open(ROOT / "data" / "eval_set.json", encoding="utf-8") as f:
        eval_set = json.load(f)
    x = [normalize(e["text"]) for e in eval_set]
    y = [e["intent"] for e in eval_set]
    pred = model.predict(x)
    print(f"\nHeld-out evaluation set ({len(y)} unseen phrasings): accuracy {accuracy_score(y, pred):.1%}\n")
    print(classification_report(y, pred, zero_division=0))
    misses = [(t, e, p) for t, e, p in zip((e["text"] for e in eval_set), y, pred) if e != p]
    for text, expected, got in misses:
        print(f"  MISS: {text!r}  expected={expected}  got={got}")


if __name__ == "__main__":
    main()
