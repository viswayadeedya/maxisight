from dataclasses import dataclass, field
from pathlib import Path

from maxisight._consts import DEFAULT_CONCURRENCY, DEFAULT_OUTPUT_DIR, USER_AGENT


@dataclass
class Configuration:
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    max_concurrency: int = DEFAULT_CONCURRENCY
    user_agent: str = USER_AGENT
