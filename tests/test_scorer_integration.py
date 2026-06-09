"""Integration test — runs scorer on real enriched data."""
import json
from pathlib import Path

import pytest

from maxisight.models import Job
from maxisight.scorer.profile import ScoringProfile
from maxisight.scorer.scorer import score_jobs

ENRICHED_PATH = Path("storage/datasets/mygreenhouse")


@pytest.mark.skipif(
    not any(ENRICHED_PATH.glob("enriched_*.json")),
    reason="No enriched data — run maxisight enrich first",
)
def test_scorer_on_real_enriched_data():
    enriched_file = next(ENRICHED_PATH.glob("enriched_*.json"))
    jobs = [Job(**j) for j in json.loads(enriched_file.read_text())[:50]]

    profile = ScoringProfile.load("storage/profiles/default.json")
    scored = score_jobs(jobs, profile)

    assert len(scored) > 0
    assert all(s.score >= profile.score_threshold for s in scored)
    assert scored[0].score >= scored[-1].score

    # Support Engineer must not leak through
    leaked = [s for s in scored
              if "support" in s.job.title.lower() and "software" not in s.job.title.lower()]
    assert len(leaked) == 0, f"Support roles leaked: {[s.job.title for s in leaked]}"

    print(f"\nScored {len(scored)} from {len(jobs)} input")
    print(f"Top: {scored[0].job.title} @ {scored[0].job.company_name} — {scored[0].score:.4f}")
