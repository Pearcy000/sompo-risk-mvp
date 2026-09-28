"""Treino em dados rotulados e regra explícita de demonstração quando não há modelo."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from .features import FEATURES, extract
from .validation import validate


def predict(features, path):
    artifact = Path(path)
    if artifact.exists():
        import joblib
        bundle = joblib.load(artifact)  # Apenas artefatos gerados pelo próprio projeto.
        p = float(bundle["model"].predict_proba([[features[k] for k in FEATURES]])[0][1])
        return p, bundle["version"]
    # Índice ilustrativo; não é uma probabilidade calibrada de sinistro.
    points = (0.10 + min(features["speed_kmh"] / 180, 1) * .15
              + max(0, features["engine_temp_c"] - 85) / 95 * .18
              + min(features["maintenance_days"] / 45, 1) * .22
              + min(features["hard_brakes"] / 10, 1) * .25
              + min(features["rain_mm"] / 30, 1) * .10)
    return min(.99, points), "demo-rule-v1"


def train(path, output):
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_fscore_support
    from sklearn.pipeline import make_pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    with open(path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) < 40:
        raise ValueError("Treino requer ao menos 40 exemplos rotulados")
    parsed = []
    for row in rows:
        if row.get("engine_temp_c") == "":
            row["engine_temp_c"] = None
        if row.get("rain_mm") == "":
            row["rain_mm"] = None
        parsed.append((validate(row), row["risk_next_24h"]))
    parsed.sort(key=lambda item: item[0]["timestamp"])
    x = [[extract(event)[key] for key in FEATURES] for event, _ in parsed]
    try:
        y = [int(label) for _, label in parsed]
    except ValueError as exc:
        raise ValueError("risk_next_24h deve ser 0 ou 1") from exc
    if any(label not in (0, 1) for label in y):
        raise ValueError("risk_next_24h deve ser 0 ou 1")
    n = len(rows)
    cut, holdout = int(n * .7), int(n * .85)
    if any(len(set(part)) < 2 for part in (y[:cut], y[cut:holdout], y[holdout:])):
        raise ValueError("Treino, validação e teste precisam conter ambas as classes")
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000))
    model.fit(x[:cut], y[:cut])
    val = model.predict_proba(x[cut:holdout])[:, 1]
    thresholds = [i / 100 for i in range(20, 81, 5)]
    # Maior precisão entre limiares com recall de pelo menos 0,8 na validação.
    eligible = []
    for threshold in thresholds:
        predicted = [int(p >= threshold) for p in val]
        precision, recall, _, _ = precision_recall_fscore_support(y[cut:holdout], predicted, average="binary", zero_division=0)
        if recall >= .8:
            eligible.append((precision, threshold))
    best = max(eligible)[1] if eligible else min(thresholds)
    test = model.predict_proba(x[holdout:])[:, 1]
    labels = [int(p >= best) for p in test]
    precision, recall, f1, _ = precision_recall_fscore_support(y[holdout:], labels, average="binary", zero_division=0)
    metrics = {"precision": round(float(precision), 4), "recall": round(float(recall), 4), "f1": round(float(f1), 4),
               "pr_auc": round(float(average_precision_score(y[holdout:], test)), 4),
               "brier": round(float(brier_score_loss(y[holdout:], test)), 4),
               "threshold_validation": best, "n_train": cut, "n_validation": holdout-cut, "n_test": n-holdout,
               "dataset_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
               "note": "Métricas obtidas apenas com o conjunto sintético; não demonstram desempenho com dados reais."}
    version = "logreg-synthetic-" + metrics["dataset_sha256"][:12]
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "version": version, "threshold": best, "features": FEATURES}, output)
    Path(output).with_suffix(".json").write_text(json.dumps({"version": version, **metrics}, indent=2), encoding="utf-8")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["train"])
    parser.add_argument("--input", required=True, help="CSV com risk_next_24h=0/1")
    parser.add_argument("--output", default="models/risk_model.joblib")
    args = parser.parse_args()
    print(json.dumps(train(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
