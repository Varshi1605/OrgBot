from __future__ import annotations

from core.rag import prompts


class AnswerGenerator:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        provider: str | None = None,
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.api_key = api_key
        self.provider = provider or ("anthropic" if api_key else "offline")
        self.base_url = base_url.rstrip("/")
        self._client = None

    def _get_client(self):
        if self.provider == "anthropic" and self.api_key and self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self.api_key)
            except Exception:  # noqa: BLE001 - fall back to offline if client build fails
                self._client = None
        return self._client

    def generate(self, question: str, evidence: list[dict]) -> str:
        if self.provider == "ollama":
            return self._generate_ollama(question, evidence)
        client = self._get_client()
        if client is not None:
            return self._generate_llm(client, question, evidence)
        return self._generate_offline(question, evidence)

    def _evidence_text(self, evidence: list[dict]) -> tuple[str, str]:
        chunks = []
        graph_facts = []
        for item in evidence:
            if item["kind"] == "graph":
                graph_facts.append(f"[{item['origin']}]\n{item['text']}")
            else:
                chunks.append(f"[{item['origin']}]\n{item['text']}")
        return "\n\n".join(chunks), "\n\n".join(graph_facts)

    def _user_prompt(self, question: str, evidence: list[dict]) -> str:
        chunks, graph_facts = self._evidence_text(evidence)
        return prompts.ANSWER_USER.format(
            question=question,
            chunks=chunks or "(no vector evidence found)",
            graph_facts=graph_facts or "(no graph facts found)",
        )

    def _generate_llm(self, client, question: str, evidence: list[dict]) -> str:
        response = client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.2,
            system=prompts.ANSWER_SYSTEM,
            messages=[{"role": "user", "content": self._user_prompt(question, evidence)}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def _generate_ollama(self, question: str, evidence: list[dict]) -> str:
        import httpx

        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 1000},
            "messages": [
                {"role": "system", "content": prompts.ANSWER_SYSTEM},
                {"role": "user", "content": self._user_prompt(question, evidence)},
            ],
        }
        try:
            with httpx.Client(timeout=600) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
        except Exception:  # noqa: BLE001 - fall back to offline if Ollama is unreachable
            return self._generate_offline(question, evidence)
        return content.strip() or self._generate_offline(question, evidence)

    def _generate_offline(self, question: str, evidence: list[dict]) -> str:
        if not evidence:
            return "No evidence found to answer the question."
        top = evidence[0]
        excerpt = top.get("text", "").strip().replace("\n", " ")[:400]
        return (
            f"Based on the retrieved evidence ({top['origin']}), the most relevant "
            f"information is: {excerpt} (offline response without LLM access.)"
        )
