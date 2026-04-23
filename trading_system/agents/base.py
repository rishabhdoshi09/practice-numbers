import os
from openai import OpenAI


class BaseAgent:
    """Thin wrapper around the Groq API using the OpenAI-compatible client."""

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set. Get a free key at console.groq.com "
                "and add it to your .env file."
            )
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

    def chat(self, system_prompt: str, user_message: str, max_tokens: int = 400) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
