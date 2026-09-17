"""Title/thumbnail packaging checks for the operator review gate."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PackagingReport:
    title_length: int
    title_truncated_risk: bool
    duplicate_terms: tuple[str, ...]
    vague_terms: tuple[str, ...]
    score: float
    notes: tuple[str, ...]


_VAGUE = {"amazing", "ultimate", "best", "crazy", "insane", "secret", "things", "stuff"}
_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "for", "is", "this", "that", "with"}


def lint_package(title: str, thumbnail_text: str = "") -> PackagingReport:
    title_words = [w.lower() for w in re.findall(r"[a-z0-9']+", title)]
    thumb_words = [w.lower() for w in re.findall(r"[a-z0-9']+", thumbnail_text)]
    title_set = {w for w in title_words if w not in _STOP}
    thumb_set = {w for w in thumb_words if w not in _STOP}
    duplicate = tuple(sorted(title_set & thumb_set))
    vague = tuple(sorted(set(title_words) & _VAGUE))
    notes: list[str] = []
    if len(title) > 80:
        notes.append("Title may truncate or become difficult to scan.")
    if duplicate:
        notes.append("Title and thumbnail repeat important words; consider complementary messaging.")
    if vague:
        notes.append("Vague words are present; replace them with a specific promise where evidence allows.")
    score = 10.0
    score -= 1.5 if len(title) > 80 else 0
    score -= min(3.0, len(duplicate) * 0.5)
    score -= min(2.0, len(vague) * 0.5)
    return PackagingReport(len(title), len(title) > 80, duplicate, vague, round(max(0.0, score), 2), tuple(notes))
