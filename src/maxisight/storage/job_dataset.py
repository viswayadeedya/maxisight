import json
from datetime import date
from pathlib import Path

from maxisight.errors import StorageError
from maxisight.models import Job, ScoredJob


class JobDataset:
    def __init__(self, output_dir: Path = Path("./storage")) -> None:
        self._output_dir = output_dir

    def save(self, jobs: list[Job], source: str, company_slug: str) -> Path:
        dest = self._output_dir / "datasets" / source
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Cannot create output directory {dest}: {e}") from e

        out_file = dest / f"{company_slug}.json"
        payload = [job.model_dump() for job in jobs]

        try:
            out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        except OSError as e:
            raise StorageError(f"Cannot write to {out_file}: {e}") from e

        return out_file

    def load(self, file: Path) -> list[Job]:
        try:
            data = json.loads(file.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise StorageError(f"Cannot read dataset {file}: {e}") from e
        return [Job(**item) for item in data]

    def load_enriched(self, filepath: str | Path) -> list[Job]:
        p = Path(filepath)
        if not p.exists():
            raise StorageError(f"Dataset not found: {p}")
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise StorageError(f"Cannot read dataset {p}: {e}") from e
        return [Job(**item) for item in data]

    def save_scored(self, scored_jobs: list[ScoredJob], source: str, query: str) -> Path:
        slug = query.lower().replace(" ", "_")
        date_str = date.today().isoformat()
        dest = self._output_dir / "datasets" / "scored"
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Cannot create scored directory {dest}: {e}") from e

        out_file = dest / f"{source}_{slug}_{date_str}.json"
        try:
            out_file.write_text(
                json.dumps(
                    [s.model_dump() for s in scored_jobs],
                    indent=2,
                    default=str,
                    ensure_ascii=False,
                )
            )
        except OSError as e:
            raise StorageError(f"Cannot write scored output to {out_file}: {e}") from e
        return out_file
