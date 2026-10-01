"""Executes SQL against Athena (real mode) or against the local retail.db
SQLite file as a stand-in (mock mode), behind the same run_query(sql) ->
list[dict] interface db.py already used - so main.py barely changes.

Mock mode is the default until a real AWS sandbox account + Secret Manager
entry exist. Set MOCK_ATHENA=false to use the real boto3/Athena path.
"""

import os
import time

MOCK_ATHENA = os.environ.get("MOCK_ATHENA", "true").lower() == "true"

ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "retail_db")
ATHENA_OUTPUT_S3 = os.environ.get("ATHENA_OUTPUT_S3", "s3://CHANGE-ME-athena-results/sql-chatbot/")
POLL_INTERVAL_SECONDS = 1
MAX_POLLS = 30


class AthenaQueryError(Exception):
    pass


def _run_query_mock(sql: str) -> list[dict]:
    # Stand-in for Athena: same schema/data, local SQLite file, so the rest
    # of the pipeline (and the eval harness) can be exercised honestly
    # without needing a live AWS account yet.
    from db import run_query as sqlite_run_query

    return sqlite_run_query(sql)


def _run_query_real(sql: str) -> list[dict]:
    import boto3

    from secrets_util import get_aws_credentials

    creds = get_aws_credentials()
    client = boto3.client(
        "athena",
        aws_access_key_id=creds["access_key_id"],
        aws_secret_access_key=creds["secret_access_key"],
        region_name=creds["region"],
    )

    start = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_S3},
    )
    query_id = start["QueryExecutionId"]

    for _ in range(MAX_POLLS):
        status = client.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "unknown error")
            raise AthenaQueryError(f"Athena query {state.lower()}: {reason}")
        time.sleep(POLL_INTERVAL_SECONDS)
    else:
        raise AthenaQueryError(f"Athena query {query_id} did not finish within {MAX_POLLS}s")

    result = client.get_query_results(QueryExecutionId=query_id)
    rows = result["ResultSet"]["Rows"]
    if not rows:
        return []

    columns = [col.get("VarCharValue", "") for col in rows[0]["Data"]]
    records = []
    for row in rows[1:]:
        values = [cell.get("VarCharValue") for cell in row["Data"]]
        records.append(dict(zip(columns, values)))
    return records


def run_query(sql: str) -> list[dict]:
    return _run_query_mock(sql) if MOCK_ATHENA else _run_query_real(sql)
