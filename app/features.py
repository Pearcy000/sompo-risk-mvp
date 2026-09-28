FEATURES = ("speed_kmh", "engine_temp_c", "temp_missing", "rain_mm", "rain_missing", "maintenance_days", "hard_brakes")


def extract(event):
    return {
        "speed_kmh": float(event["speed_kmh"]),
        "engine_temp_c": float(event["engine_temp_c"] if event.get("engine_temp_c") is not None else 85),
        "temp_missing": int(event.get("engine_temp_c") is None),
        "rain_mm": float(event.get("rain_mm") or 0),
        "rain_missing": int(event.get("rain_mm") is None),
        "maintenance_days": float(event["maintenance_days"]),
        "hard_brakes": float(event.get("hard_brakes") or 0),
    }
