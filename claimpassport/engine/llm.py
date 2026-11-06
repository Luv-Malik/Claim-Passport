"""Optional LLM helper. It is used ONLY to propose extra rewrites. It never decides anything.

Privacy by design:
- it is off unless ANTHROPIC_API_KEY is set (and CP_USE_LLM=1),
- only one sentence, the issue text and the approved statement are sent,
- personal data is masked first, and confidential facts are replaced by a placeholder,
- every call is written to the AI transparency log."""
import json
import urllib.request

from ..security import mask_pii


class LLMClient:
    def __init__(self, cfg):
        self.key = cfg.get("ANTHROPIC_API_KEY") or ""
        self.model = cfg.get("LLM_MODEL", "claude-sonnet-5-5")
        self.enabled = bool(self.key) and bool(cfg.get("USE_LLM", True))

    @property
    def available(self):
        return self.enabled

    def _post(self, prompt):  # pragma: no cover (network)
        body = json.dumps({"model": self.model, "max_tokens": 400,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
                                     headers={"x-api-key": self.key, "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data.get("content", []))

    def rewrite(self, sentence, issue, source_statement=None):
        """Return (list_of_rewrites, masked_items). Empty list on any problem."""
        sentence_m, n1 = mask_pii(sentence)
        source = source_statement if source_statement else "(none)"
        prompt = (
            "You help a brand team fix one sentence. Rewrite it in 2 different ways that fix the issue but keep the "
            "writer's meaning and friendly, professional tone. Use ONLY facts from SOURCE. Do not add new claims.\n"
            f"SENTENCE: {sentence_m}\nISSUE: {issue}\nSOURCE: {source}\n"
            'Answer with a JSON list of 2 strings and nothing else.')
        try:
            text = self._post(prompt).strip()
            text = text[text.index("["): text.rindex("]") + 1]
            items = [str(x).strip() for x in json.loads(text) if str(x).strip()]
            return items[:2], n1
        except Exception:
            return [], n1
