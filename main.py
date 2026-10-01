import sqlite3

from fastapi import FastAPI
from pydantic import BaseModel

from athena_client import MOCK_ATHENA, AthenaQueryError, run_query
from llm import generate_explanation, generate_sql
from prompt import build_explanation_prompt, build_generation_prompt, build_retry_prompt
from sql_guard import UnsafeQueryError, validate_select_only

QUERY_ERRORS = (UnsafeQueryError, AthenaQueryError, sqlite3.Error)

app = FastAPI(title="Retail Sales & Catalog Query Assistant")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    sql: str
    row_count: int
    rows: list[dict]
    answer: str
    retried: bool


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "athena_mode": "mock" if MOCK_ATHENA else "live"}


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    question = payload.question

    raw_sql = generate_sql(build_generation_prompt(question))
    if raw_sql.strip().upper() == "NOT_ANSWERABLE":
        return AskResponse(
            question=question, sql="", row_count=0, rows=[],
            answer="I can't answer that from the products/sales data I have access to.",
            retried=False,
        )

    retried = False
    try:
        safe_sql = validate_select_only(raw_sql)
        rows = run_query(safe_sql)
    except QUERY_ERRORS as first_error:
        retried = True
        try:
            retry_sql = generate_sql(build_retry_prompt(question, raw_sql, str(first_error)))
            safe_sql = validate_select_only(retry_sql)
            rows = run_query(safe_sql)
        except QUERY_ERRORS as second_error:
            return AskResponse(
                question=question, sql=raw_sql, row_count=0, rows=[],
                answer=f"Couldn't produce a safe query after one retry ({second_error}).",
                retried=True,
            )

    explanation = generate_explanation(build_explanation_prompt(question, safe_sql, rows))

    return AskResponse(
        question=question,
        sql=safe_sql,
        row_count=len(rows),
        rows=rows[:20],
        answer=explanation,
        retried=retried,
    )
