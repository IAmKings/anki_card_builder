"""Pipeline configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Pipeline configuration."""
    data_dir: Path = Path("data")
    output_dir: Path = Path("output")
    output_file: str = "Android面试卡组.apkg"

    # genanki model/deck IDs (generate once, then hardcode for stability)
    basic_model_id: int = 1607392319
    cloze_model_id: int = 1607892320
    parent_deck_id: int = 2059400110

    # Deduplication threshold
    dedup_threshold: float = 0.85

    # Minimum cards per PDF
    min_cards_per_pdf: int = 100

    # API configuration
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    api_model: str = "claude-sonnet-4-20250514"


# Global config
CONFIG = Config()
