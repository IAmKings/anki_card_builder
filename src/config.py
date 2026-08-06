"""Pipeline configuration.

API key loading order (first wins):
1. Environment variable ANTHROPIC_API_KEY
2. .env file in project root (gitignored)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_value(key_name: str) -> str:
    """Load a value from env var or .env file."""
    value = os.environ.get(key_name, "")
    if value:
        return value
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == key_name:
                    return v.strip().strip('"').strip("'")
    return ""


def _load_deepseek_api_key() -> str:
    """Load DEEPSEEK_API_KEY from env or .env file."""
    return _load_env_value("DEEPSEEK_API_KEY")


def _load_anthropic_api_key() -> str:
    """Load ANTHROPIC_API_KEY from env or .env file."""
    return _load_env_value("ANTHROPIC_API_KEY")


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

    # 山河集-specific model/deck IDs (separate range to avoid conflicts)
    shanheji_basic_model_id: int = 1807392319
    shanheji_cloze_model_id: int = 1807892320
    shanheji_parent_deck_id: int = 2859400110

    # MQTT-specific model/deck IDs (separate range to avoid conflicts)
    mqtt_basic_model_id: int = 1907392319
    mqtt_parent_deck_id: int = 3859400110

    # Deduplication threshold
    dedup_threshold: float = 0.85

    # Minimum cards per PDF
    min_cards_per_pdf: int = 100

    # API configuration (loaded from env or .env file)
    # Anthropic
    anthropic_api_key: str = field(default_factory=_load_anthropic_api_key)
    anthropic_api_model: str = "claude-sonnet-4-20250514"
    # DeepSeek (cheaper, preferred for batch generation)
    deepseek_api_key: str = field(default_factory=_load_deepseek_api_key)
    deepseek_api_model: str = "deepseek-chat"

    # Backward compatibility aliases (指向 Anthropic, set in __post_init__)
    api_key: str = field(init=False)
    api_model: str = field(init=False)

    def __post_init__(self):
        self.api_key = self.anthropic_api_key
        self.api_model = self.anthropic_api_model


# Global config
CONFIG = Config()
