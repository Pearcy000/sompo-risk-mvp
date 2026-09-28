"""Gera base acadêmica reproduzível; rótulos simulam risco e não são observações reais."""
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generate(path, count=400, seed=42):
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fields = ["event_id", "equipment_id", "timestamp", "region", "operation_type", "speed_kmh", "engine_temp_c", "rain_mm", "maintenance_days", "hard_brakes", "risk_next_24h"]
    rows = []
    for i in range(count):
        speed = round(rng.uniform(15, 125), 1)
        temp = round(rng.uniform(65, 130), 1)
        rain = round(rng.uniform(0, 35), 1)
        maintenance = rng.randrange(0, 50)
        brakes = rng.randrange(0, 12)
        logit = -5.0 + .024 * speed + .025 * (temp - 80) + .04 * maintenance + .19 * brakes + .02 * rain
        probability = 1 / (1 + math.exp(-logit))
        rows.append([f"synthetic-{i:04d}", f"EQ-{i%35:03d}", (start + timedelta(hours=i*6)).isoformat(),
                     rng.choice(["Norte", "Nordeste", "Sul", "Sudeste"]), rng.choice(["urbana", "rodoviaria", "industrial", "rural"]),
                     speed, temp if i % 17 else "", rain, maintenance, brakes, int(rng.random() < probability)])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    generate("data/raw/synthetic_labeled.csv")
