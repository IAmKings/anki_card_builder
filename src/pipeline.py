"""Pipeline orchestration for the card builder."""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

from .config import CONFIG
from .models import Flashcard
from .parsers import InterviewPDFParser, KnowledgePDFParser, TxtParser, KotlinMDParser
from .processing import Deduplicator, QualityFilter
from .export import AnkiExporter

log = logging.getLogger(__name__)


def discover_source_files(data_dir: Path) -> List[Path]:
    """Discover all PDF, TXT, and MD files in the data directory."""
    files: List[Path] = []
    for ext in ["*.pdf", "*.txt", "*.md"]:
        files.extend(data_dir.glob(ext))
    files.sort(key=lambda p: p.name)
    return files


def process_file(filepath: Path) -> List[Flashcard]:
    """Process a single source file and return flashcards."""
    ext = filepath.suffix.lower()

    if ext == ".md":
        parser = KotlinMDParser(filepath)
    elif ext == ".pdf":
        name_lower = filepath.stem.lower()
        if "面试" in name_lower or "阿里巴巴" in name_lower:
            parser = InterviewPDFParser(filepath)
        else:
            parser = KnowledgePDFParser(filepath)
    elif ext == ".txt":
        parser = TxtParser(filepath)
    else:
        log.warning(f"Unsupported file type: {filepath}")
        return []

    try:
        return parser.parse()
    except Exception as e:
        log.error(f"Error processing {filepath}: {e}")
        import traceback
        log.error(traceback.format_exc())
        return []


def generate_summary_report(cards: List[Flashcard], output_path: Path):
    """Generate a summary report of the cards."""
    lines = []
    lines.append("=" * 60)
    lines.append("Anki 卡片生成报告")
    lines.append("=" * 60)
    lines.append(f"生成时间: 2026-06-08")
    lines.append(f"总卡片数: {len(cards)}")
    lines.append(f"输出文件: {output_path}")
    lines.append("")

    sources: Dict[str, int] = {}
    for card in cards:
        sources[card.source_file] = sources.get(card.source_file, 0) + 1

    lines.append("--- 按来源统计 ---")
    for src, count in sorted(sources.items()):
        lines.append(f"  {src}: {count} 张卡片")

    decks: Dict[str, int] = {}
    for card in cards:
        decks[card.deck_name] = decks.get(card.deck_name, 0) + 1

    lines.append("\n--- 按牌组统计 ---")
    for deck, count in sorted(decks.items()):
        lines.append(f"  {deck}: {count} 张卡片")

    lines.append("\n--- 抽样卡片 (前10张) ---")
    for i, card in enumerate(cards[:10]):
        lines.append(f"\n卡片 {i+1}:")
        lines.append(f"  牌组: {card.deck_name}")
        lines.append(f"  问题: {card.front[:80]}...")
        lines.append(f"  答案: {card.back[:80]}...")
        lines.append(f"  标签: {', '.join(card.tags)}")
        lines.append(f"  来源: {card.source_file} > {card.source_section}")

    lines.append("\n" + "=" * 60)

    report = '\n'.join(lines)
    report_path = output_path.with_suffix('.txt')
    report_path.write_text(report, encoding='utf-8')
    log.info(f"Report written to {report_path}")

    print()
    print(report)


def check_api_key():
    """Check and report API key status."""
    if CONFIG.api_key:
        log.info(f"Anthropic API key found ({CONFIG.api_key[:8]}...{CONFIG.api_key[-4:]})")
        log.info("AI generation will be used for knowledge PDF and TXT files.")
        return True
    else:
        log.warning("No ANTHROPIC_API_KEY found in environment.")
        log.warning("AI generation will be skipped for knowledge PDF and TXT files.")
        log.warning("Only the interview PDF will be fully processed.")
        log.warning("To enable AI generation, set: export ANTHROPIC_API_KEY='your-key-here'")
        return False


def main():
    """Main pipeline entry point."""
    log.info("=" * 50)
    log.info("PDF-to-Anki Card Builder Pipeline")
    log.info("=" * 50)

    check_api_key()
    print()

    data_dir = CONFIG.data_dir.resolve()
    if not data_dir.exists():
        log.error(f"Data directory not found: {data_dir}")
        sys.exit(1)

    source_files = discover_source_files(data_dir)
    if not source_files:
        log.error(f"No PDF or TXT files found in {data_dir}")
        sys.exit(1)

    log.info(f"Found {len(source_files)} source files:")
    for f in source_files:
        log.info(f"  - {f.name} ({f.stat().st_size / 1024:.0f} KB)")
    print()

    log.info("Phase 1: Extraction and Parsing")
    log.info("-" * 40)
    all_cards: List[Flashcard] = []
    source_stats: Dict[str, int] = {}

    for filepath in source_files:
        cards = process_file(filepath)
        all_cards.extend(cards)
        source_stats[filepath.name] = len(cards)
        log.info(f"  -> {filepath.name}: {len(cards)} cards")

    print()

    log.info("Phase 2: Quality Check")
    log.info("-" * 40)

    pdf_files = [f for f in source_files if f.suffix.lower() == '.pdf']
    for pdf in pdf_files:
        count = source_stats.get(pdf.name, 0)
        if count < CONFIG.min_cards_per_pdf:
            log.warning(f"  {pdf.name}: only {count} cards (minimum: {CONFIG.min_cards_per_pdf})")
        else:
            log.info(f"  {pdf.name}: {count} cards (meets minimum)")

    filtered_cards = QualityFilter.validate(all_cards)
    log.info(f"  Quality filter: {len(all_cards)} -> {len(filtered_cards)} cards")

    log.info(f"\nPhase 3: Deduplication")
    log.info("-" * 40)
    deduper = Deduplicator(threshold=CONFIG.dedup_threshold)
    unique_cards = deduper.deduplicate(filtered_cards)

    print()

    log.info("Phase 4: Anki Export")
    log.info("-" * 40)
    output_dir = CONFIG.output_dir.resolve()
    output_path = output_dir / CONFIG.output_file

    exporter = AnkiExporter()
    result_path = exporter.export(unique_cards, output_path)

    print()

    generate_summary_report(unique_cards, output_path)

    log.info("Pipeline completed successfully!")
    log.info(f"Output: {result_path}")
    log.info(f"Total cards: {len(unique_cards)}")

    return result_path
