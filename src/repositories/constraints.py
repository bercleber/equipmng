from sqlalchemy.exc import IntegrityError


def is_duplicate(err: IntegrityError) -> bool:
    code = err.orig.args[0] if err.orig.args else None
    return code == 1062 or getattr(err.orig, "sqlite_errorname", None) in {
        "SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY",
    }


def is_missing_reference(err: IntegrityError) -> bool:
    code = err.orig.args[0] if err.orig.args else None
    return code == 1452 or getattr(err.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_FOREIGNKEY"


def is_referenced(err: IntegrityError) -> bool:
    code = err.orig.args[0] if err.orig.args else None
    return code == 1451 or getattr(err.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_FOREIGNKEY"
