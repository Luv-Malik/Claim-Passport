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

    def judge(self, sentence, candidates):
        """Ask whether the approved facts support ONE sentence. Returns (answer_dict_or_None, masked_items).
        The answer must be JSON with verdict, fact_id, quote (words copied from that fact) and reason.
        The caller (judge.py) checks the citation; an uncited answer is never trusted."""
        sentence_m, n1 = mask_pii(sentence)
        facts = "\n".join(f"[{c['id']}] {c['statement']}" for c in candidates)
        prompt = (
            "You check one marketing sentence against a list of APPROVED FACTS. Decide if the facts support the "
            "sentence, contradict it, or are unrelated to it. Be strict: say 'supports' only when a fact says the same "
            "thing, and 'contradicts' only when a fact clearly says something different about the same subject.\n"
            f"SENTENCE: {sentence_m}\nAPPROVED FACTS:\n{facts}\n"
            'Answer with ONE JSON object and nothing else: {"verdict": "supports|contradicts|unrelated|unsure", '
            '"fact_id": <id of the fact you relied on, or null>, "quote": "<words copied exactly from that fact>", '
            '"reason": "<one short sentence>"}')
        try:
            text = self._post(prompt).strip()
            return json.loads(text[text.index("{"): text.rindex("}") + 1]), n1
        except Exception:
            return None, n1
