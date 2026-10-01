SCHEMA_CONTEXT = """
You are writing Athena SQL (Presto/Trino dialect) against the Glue Catalog
database "retail_db", which has exactly these two tables. Do not assume any
other table or column exists. Tables may be referenced unqualified
(products) or schema-qualified (retail_db.products) - either is fine.

TABLE products
  sku          string   -- e.g. "SKU-1001"
  name         string   -- product display name
  category     string   -- one of: Beverages, Snacks, Household, Personal Care, Frozen Foods
  unit_price   double   -- price in THB

TABLE sales
  order_id     bigint
  sku          string   -- foreign key -> products.sku
  region       string   -- one of: Bangkok, Chiang Mai, Phuket, Khon Kaen
  quantity     int
  order_date   date     -- e.g. DATE '2026-03-14'
  returned     int      -- 1 if the order was returned, else 0

Presto/Trino notes: there is no AUTOINCREMENT; date literals use
DATE 'YYYY-MM-DD'; string concatenation uses ||, not +.
""".strip()

SYSTEM_INSTRUCTION = """
You translate a retail analyst's question into exactly one SQLite SELECT
statement, using only the schema provided. Rules:
- Output ONLY the raw SQL, no markdown fences, no commentary.
- Never write INSERT, UPDATE, DELETE, DROP, ALTER, or any statement other
  than SELECT.
- Only reference the tables and columns given in the schema.
- Unless the question explicitly asks about returns, do NOT filter on the
  `returned` column - "quantity sold" means every order line, returned or
  not, unless the analyst says otherwise.
- If the question cannot be answered from this schema, output exactly:
  NOT_ANSWERABLE
""".strip()


def build_generation_prompt(question: str) -> str:
    return f"{SCHEMA_CONTEXT}\n\nQuestion: {question}\n\nSQL:"


def build_retry_prompt(question: str, failed_sql: str, db_error: str) -> str:
    return (
        f"{SCHEMA_CONTEXT}\n\n"
        f"Question: {question}\n\n"
        f"You previously generated this SQL:\n{failed_sql}\n\n"
        f"It failed with this database error:\n{db_error}\n\n"
        f"Fix it and output ONLY the corrected SQL, no commentary.\nSQL:"
    )


def build_explanation_prompt(question: str, sql: str, rows: list[dict]) -> str:
    preview = rows[:5]
    return (
        "In 1-2 plain-English sentences, answer the analyst's question using "
        "the query result below. Do not mention SQL or tables.\n\n"
        f"Question: {question}\nResult (first rows): {preview}\nTotal rows: {len(rows)}"
    )
