import sqlparse
from sqlparse.sql import Identifier, IdentifierList
from sqlparse.tokens import DML, Keyword

ALLOWED_TABLES = {"products", "sales"}


class UnsafeQueryError(Exception):
    pass


def _extract_table_names(parsed) -> set[str]:
    tables = set()
    from_seen = False
    for token in parsed.tokens:
        if from_seen:
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    tables.add(identifier.get_real_name())
            elif isinstance(token, Identifier):
                tables.add(token.get_real_name())
            elif token.ttype is Keyword:
                from_seen = False
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
            from_seen = True
    return tables


def validate_select_only(sql: str) -> str:
    """Raise UnsafeQueryError unless `sql` is a single, read-only SELECT
    against tables on the whitelist. Returns the cleaned statement."""
    statements = [s for s in sqlparse.parse(sql) if s.token_first(skip_cm=True)]

    if len(statements) != 1:
        raise UnsafeQueryError("Only a single statement is allowed per request.")

    stmt = statements[0]
    first_token = stmt.token_first(skip_cm=True)

    if first_token.ttype is not DML or first_token.value.upper() != "SELECT":
        raise UnsafeQueryError(
            f"Only SELECT statements are allowed; got: {first_token.value.upper()}"
        )

    banned = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "ATTACH", "PRAGMA"}
    upper_sql = sql.upper()
    for word in banned:
        if word in upper_sql:
            raise UnsafeQueryError(f"Disallowed keyword detected: {word}")

    tables = _extract_table_names(stmt)
    disallowed = tables - ALLOWED_TABLES
    if disallowed:
        raise UnsafeQueryError(f"Query references table(s) not on the whitelist: {disallowed}")

    return str(stmt).strip().rstrip(";")
