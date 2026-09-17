"""Evidence-aware YouTube hook analysis.

This is a ContentOS implementation inspired by useful patterns in the public
youtube-agent-skill project. It does not copy that project's code or claim
that a heuristic predicts performance.
"""

from dataclasses import dataclass
import re


FORMULAS = (
    "statistic", "result", "mistake", "contrarian", "reveal", "superlative",
    "clock", "experiment", "question", "before_after", "teardown", "stack",
    "warning", "list", "receipt", "insider", "impossible", "comparison",
    "origin", "deadline", "direct_address",
)

_PATTERNS = {
    "statistic": (r"\b\d+(?:\.\d+)?\s?%", r"\b\d+\s+(?:out of|in)\s+\d+\b"),
    "result": (r"\bwent from\b", r"\b(?:channel|creator|video)\b.*\b\d+\b"),
    "mistake": (r"\b(?:mistake|wrong|stop doing|you(?:'re| are)\s+doing)\b",),
    "contrarian": (r"\beveryone\s+(?:says|thinks|tells)\b", r"\b(?:actually wrong|nobody tells)\b"),
    "reveal": (r"\b(?:show you|here(?:'s| is)|on screen)\b",),
    "superlative": (r"\b(?:best|worst|fastest|easiest|only|number one)\b",),
    "clock": (r"\b(?:next|under)\s+\d+\s+(?:seconds|minutes|hours)\b", r"\bby the end\b"),
    "experiment": (r"\bI\s+(?:tried|tested|spent|let|gave)\b", r"\bfor\s+\d+\s+(?:days|weeks|months)\b"),
    "question": (r"^(?:why|how|what|when|should|can|do|does|is)\b", r"\?\s*$"),
    "before_after": (r"\bbefore\b.*\bafter\b", r"\bthis was\b.*\bthis is\b"),
    "teardown": (r"\b(?:break|broke|breaking)\s+(?:it\s+)?down\b", r"\bteardown\b"),
    "stack": (r"\b\w+\s+(?:plus|and|\+)\s+\w+\b", r"\bcombine\b"),
    "warning": (r"\b(?:do not|don't|before you|stop)\b",),
    "list": (r"^\d+\s+\w+", r"\b(?:here are|these are)\s+\d+\b"),
    "receipt": (r"\b(?:screenshot|proof|receipt)\b", r"\bthis is (?:the|my)\b"),
    "insider": (r"\b(?:hidden|buried|almost nobody|most people)\b",),
    "impossible": (r"\b(?:without|never|zero)\b", r"\bin one\b"),
    "comparison": (r"\b(?:vs\.?|versus)\b", r"\bwhich (?:one )?(?:is|wins)\b"),
    "origin": (r"\bevery\s+(?:video|post).*\bstarts\b", r"\bit all started\b"),
    "deadline": (r"\b(?:this|next)\s+(?:week|month|year)\b", r"\b(?:as of|no longer|is changing)\b"),
    "direct_address": (r"^if you\b", r"\bfor (?:anyone|people) who\b"),
}


@dataclass(frozen=True)
class HookAnalysis:
    hook: str
    formula: str
    score: float
    evidence_strength: float
    curiosity: float
    clarity: float
    notes: tuple[str, ...]


def analyze_hook(hook: str) -> HookAnalysis:
    text = " ".join(hook.strip().split())
    lower = text.lower()
    matches = {name for name, patterns in _PATTERNS.items() if any(re.search(p, lower, re.I) for p in patterns)}
    formula = next((name for name in FORMULAS if name in matches), "direct_address")

    evidence = 8.0 if re.search(r"\b\d+(?:\.\d+)?\b", lower) else 5.5
    clarity = min(10.0, 4.0 + min(len(text), 100) / 20)
    curiosity = 5.0
    if "?" in text:
        curiosity += 1.5
    if any(x in lower for x in ("but", "until", "why", "how", "actually", "secret", "mistake")):
        curiosity += 1.5
    if len(text) <= 140:
        clarity += 1.0
    notes: list[str] = []
    if len(text) > 180:
        notes.append("Hook may be too long for a clean opening.")
    if re.search(r"\b\d+(?:\.\d+)?\b", text) and not re.search(r"%|out of|source|according", lower):
        notes.append("Numeric claim needs a verifiable source before publication.")
    if not any(re.search(p, lower, re.I) for p in _PATTERNS[formula]):
        notes.append("Formula match is weak; treat the classification as a heuristic.")
    score = round(min(10.0, evidence * 0.30 + curiosity * 0.40 + clarity * 0.30), 2)
    return HookAnalysis(text, formula, score, evidence, curiosity, clarity, tuple(notes))


def rank_hooks(hooks: list[str]) -> list[HookAnalysis]:
    """Rank candidate hooks for review; this is not a performance predictor."""
    return sorted((analyze_hook(h) for h in hooks), key=lambda x: x.score, reverse=True)
