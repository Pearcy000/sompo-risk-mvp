from datetime import datetime, timezone

OPERATIONS = {"urbana", "rodoviaria", "industrial", "rural"}


class InvalidEvent(ValueError):
    pass


def validate(event, known_equipment=None):
    required = ("event_id", "equipment_id", "timestamp", "region", "operation_type", "speed_kmh", "maintenance_days")
    missing = [key for key in required if key not in event or event[key] is None or event[key] == ""]
    if missing:
        raise InvalidEvent("Campos obrigatórios ausentes: " + ", ".join(missing))
    result = dict(event)
    for key in ("event_id", "equipment_id", "region"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise InvalidEvent(f"{key} deve ser texto não vazio")
        result[key] = result[key].strip()
    if known_equipment is not None and result["equipment_id"] not in known_equipment:
        raise InvalidEvent("Equipamento não cadastrado")
    if result["operation_type"] not in OPERATIONS:
        raise InvalidEvent("Tipo de operação inválido")
    try:
        stamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            raise InvalidEvent("timestamp deve estar em UTC e não pode estar no futuro")
        result["timestamp"] = stamp.astimezone(timezone.utc).isoformat()
        for key, low, high in (("speed_kmh", 0, 180), ("engine_temp_c", -20, 180), ("rain_mm", 0, 500), ("maintenance_days", 0, 3650), ("hard_brakes", 0, 100)):
            if key in ("engine_temp_c", "rain_mm") and result.get(key) is None:
                continue
            value = float(result.get(key, 0))
            if not low <= value <= high:
                raise InvalidEvent(f"{key} fora do intervalo [{low}, {high}]")
            result[key] = value
    except (TypeError, ValueError) as exc:
        if isinstance(exc, InvalidEvent):
            raise
        raise InvalidEvent("Tipo ou timestamp inválido") from exc
    return result
