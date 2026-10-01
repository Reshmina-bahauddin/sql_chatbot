import json
import os
from functools import lru_cache

GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "thinking-land-401107")
SECRET_NAME = os.environ.get("AWS_CREDS_SECRET_NAME", "athena-chatbot-aws-creds")


@lru_cache(maxsize=1)
def get_aws_credentials() -> dict:
    """Fetch {"access_key_id": ..., "secret_access_key": ..., "region": ...}
    from GCP Secret Manager. Cached in-process so we hit Secret Manager once
    per running instance, not once per request."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"
    response = client.access_secret_version(name=name)
    payload = response.payload.data.decode("utf-8")
    creds = json.loads(payload)

    for key in ("access_key_id", "secret_access_key", "region"):
        if key not in creds:
            raise ValueError(f"Secret {SECRET_NAME} is missing required key: {key}")
    return creds
