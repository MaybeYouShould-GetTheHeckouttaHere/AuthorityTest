"""Google Cloud Vertex AI (Gemini) provider.

Uses Vertex AI's `generateContent` REST endpoint:
https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/function-calling

Authentication uses a bearer access token (e.g. from
`gcloud auth print-access-token`) rather than an API key, since Vertex AI
uses Google Cloud IAM rather than Google AI Studio API keys.

Required environment variables:
- `GOOGLE_VERTEX_ACCESS_TOKEN`, OAuth2 access token.
- `GOOGLE_CLOUD_PROJECT`, GCP project ID.
- `GOOGLE_CLOUD_LOCATION`, region (defaults to "us-central1").
"""
import os

from API.providers import _gemini_compatible

URL_TEMPLATE = (
    "https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
    "/locations/{location}/publishers/google/models/{model}:generateContent"
)


def call(messages, tools=None, model=None, **params):
    def build_request(model):
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        token = os.environ["GOOGLE_VERTEX_ACCESS_TOKEN"]
        url = URL_TEMPLATE.format(project=project, location=location, model=model)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        return url, headers

    return _gemini_compatible.call(messages, tools=tools, model=model, build_request=build_request, **params)
