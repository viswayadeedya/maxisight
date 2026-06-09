import json
from pathlib import Path

from pydantic import BaseModel, Field


class ScoringProfile(BaseModel):
    target_titles: list[str]
    skill_weights: dict[str, float] = Field(default_factory=dict)
    level: str = "senior"
    freshness_halflife_hours: float = 24.0
    score_threshold: float = 0.25
    top_n: int = 50
    blocklist_companies: list[str] = Field(default_factory=list)
    watchlist_companies: list[str] = Field(default_factory=list)
    blocklist_keywords: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str = "storage/profiles/default.json") -> "ScoringProfile":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Profile not found at {p}")
        return cls(**json.loads(p.read_text()))

    def extract_title_keywords(self) -> set[str]:
        """Extract meaningful keywords from target_titles, stripping generic role words."""
        GENERIC_WORDS = {
            "engineer", "developer", "programmer", "senior", "junior",
            "staff", "principal", "lead", "sr", "jr", "ii", "iii", "iv",
            "associate", "mid", "entry",
        }
        keywords = set()
        for title in self.target_titles:
            for word in title.lower().split():
                if word not in GENERIC_WORDS and len(word) > 2:
                    keywords.add(word)
        return keywords

    def load_resume_text(self, path: str = "storage/profiles/resume.txt") -> str:
        p = Path(path)
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")
