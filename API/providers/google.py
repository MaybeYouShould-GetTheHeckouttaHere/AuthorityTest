"""Google AI Studio (Generative Language API) provider.

https://ai.google.dev/gemini-api/docs/function-calling
"""
import os

from API.providers import _gemini_compatible

URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def call(messages, tools=None, model=None, **params):
    def build_request(model):
        api_key = os.environ["GOOGLE_API_KEY"]
        url = URL_TEMPLATE.format(model=model)
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        return url, headers

    return _gemini_compatible.call(messages, tools=tools, model=model, build_request=build_request, **params)
