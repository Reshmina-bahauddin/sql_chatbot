# Retail SQL Chatbot

A natural-language-to-SQL assistant over a small retail dataset (products and
sales). An analyst asks a question in plain English. Gemini (via Vertex AI)
writes a SQL query, a safety guard checks that it is a read-only `SELECT`
against whitelisted tables, the query runs against Athena (or a local SQLite
stand-in), and Gemini summarizes the result in a sentence or two.

Built with FastAPI, `google-genai`, `sqlparse`, and `boto3`.

## How a request flows

```
POST /ask {"question": "..."}
   │
   ├─ prompt.build_generation_prompt   schema + question
   ├─ llm.generate_sql                 Gemini → raw SQL (or NOT_ANSWERABLE)
   ├─ sql_guard.validate_select_only   single SELECT, no banned keywords, whitelisted tables
   ├─ athena_client.run_query          mock (SQLite) or real Athena
   │     └─ on guard/DB error: one retry, sending the failed SQL + error back to Gemini
   ├─ prompt.build_explanation_prompt  question + SQL + first 5 rows
   └─ llm.generate_explanation         plain-English answer
```

If the model replies `NOT_ANSWERABLE`, the API returns a polite refusal and
runs no query. If the retry also fails, the response carries the error
message and no rows.

## Project layout

| File | Purpose |
|---|---|
| `main.py` | FastAPI app and endpoints; holds the generate → validate → run → explain pipeline with a single retry. |
| `llm.py` | Vertex AI Gemini client. Temperature is 0 and thinking is disabled (thinking tokens count against `max_output_tokens` and were truncating answers). Strips markdown fences from generated SQL. |
| `prompt.py` | Schema context, system instruction, and the builders for the generation, retry, and explanation prompts. |
| `sql_guard.py` | `validate_select_only()`: rejects multiple statements, anything other than `SELECT`, banned keywords (`INSERT`, `DROP`, `PRAGMA`, …), and tables outside `ALLOWED_TABLES = {"products", "sales"}`. |
| `athena_client.py` | `run_query(sql) -> list[dict]`. In mock mode it delegates to `db.py`; in real mode it calls Athena through boto3, polls once per second for up to 30 s, and maps the result rows to dicts. |
| `db.py` | Read-only SQLite query runner over `retail.db`. |
| `secrets_util.py` | Fetches AWS credentials (`access_key_id`, `secret_access_key`, `region`) from GCP Secret Manager and caches them per process. |
| `seed_db.py` | Builds `retail.db` with deterministic sample data (seed 7): 40 products and 2,000 sales rows for 2026. |
| `eval.py` | Golden-set evaluation that compares query **results**, not SQL text. |

## Data model

**products**: `sku`, `name`, `category` (Beverages, Snacks, Household,
Personal Care, Frozen Foods), `unit_price` (THB)

**sales**: `order_id`, `sku` → `products.sku`, `region` (Bangkok, Chiang Mai,
Phuket, Khon Kaen), `quantity`, `order_date`, `returned` (0/1)

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/health` | `{"status": "ok", "athena_mode": "mock" \| "live"}` |
| `GET` | `/tables` | `{"queryable_tables": [...]}`, the SQL guard whitelist |
| `GET` | `/categories` | `{"categories": [...]}`, the distinct product categories, sorted |
| `POST` | `/ask` | `{question, sql, row_count, rows (first 20), answer, retried}` |

Example:

```bash
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"question": "Which region had the most orders?"}'
```

## Setup

The repo has no `requirements.txt` yet. Install these packages:

```bash
python -m venv venv
venv\Scripts\activate            # Windows (source venv/bin/activate elsewhere)
pip install fastapi uvicorn google-genai sqlparse boto3 google-cloud-secret-manager

python seed_db.py                # creates retail.db (gitignored)
gcloud auth application-default login   # Vertex AI credentials
uvicorn main:app --reload
```

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `thinking-land-401107` | Vertex AI, Secret Manager |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI |
| `SQL_CHATBOT_MODEL` | `gemini-2.5-flash` | Gemini model |
| `MOCK_ATHENA` | `true` | `true` runs against local SQLite, `false` against real Athena |
| `ATHENA_DATABASE` | `retail_db` | Athena |
| `ATHENA_OUTPUT_S3` | `s3://CHANGE-ME-athena-results/sql-chatbot/` | Athena results location; **set this for live mode** |
| `AWS_CREDS_SECRET_NAME` | `athena-chatbot-aws-creds` | Secret Manager entry holding the AWS credentials as JSON |

## Evaluation

```bash
python eval.py
```

This runs 8 golden questions through generate → guard → execute and compares
the rows against hand-written ground-truth SQL. A result passes if every
expected value appears in a matching row; extra columns are allowed and
floats are rounded to 2 decimal places. The script prints a result-match
rate. It always queries the local SQLite DB through `db.run_query`,
regardless of `MOCK_ATHENA`.

## Known limitations

- `sql_guard` checks banned keywords as substrings of the whole query, so a
  harmless identifier such as `created_at` or `update_time` is rejected.
- Table extraction only inspects top-level `FROM`/`JOIN` tokens. Tables
  inside subqueries or CTEs are not checked against the whitelist.
- `prompt.py` describes the schema in Athena (Presto/Trino) terms, while the
  system instruction asks for SQLite. Simple queries work on both, but
  dialect-specific syntax (dates, string functions) may break on one backend.
- Live-mode Athena returns every value as a string, while mock mode returns
  native types.
- `GET /categories` has no error handling, so a backend failure surfaces as
  an HTTP 500.
