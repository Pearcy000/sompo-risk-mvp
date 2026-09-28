import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def chain(previous, record):
    return hashlib.sha256((previous + digest(record)).encode()).hexdigest()


def verify(db):
    """Verifica o encadeamento armazenado; não protege contra reescrita total do banco."""
    previous = ""
    for row in db.execute("SELECT record,previous_hash,entry_hash FROM audit_log ORDER BY id"):
        record = json.loads(row["record"])
        if row["previous_hash"] != previous or row["entry_hash"] != chain(previous, record):
            return False
        previous = row["entry_hash"]
    return True
