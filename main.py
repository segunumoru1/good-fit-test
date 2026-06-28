"""
Entry point — runs Part A (extraction) then Part B (ranking) and writes
a combined results.json to the output/ folder.

Usage:
    python main.py

Requires:
    GROQ_API_KEY set in your .env file (loaded automatically).
"""

import json
import logging
import os
import pathlib
import sys

from dotenv import load_dotenv

# Initialize logging for the entire pipeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("main")

# Load environment variables
load_dotenv()

from src.extractor import extract_driver_profile
from src.ranker import load_loads, rank_loads

HERE = pathlib.Path(__file__).parent
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    logger.info("=" * 60)
    logger.info("AI Dispatcher - Good Fit Test (Groq Edition)")
    logger.info("=" * 60)

    # Validate environment variable
    if not os.environ.get("GROQ_API_KEY"):
        logger.error("Missing GROQ_API_KEY environment variable. Please make sure it is defined in your .env file.")
        sys.exit(1)

    workbook_path = DATA_DIR / "Good_fit_test_clean.xlsx"

    # ── Part A: Extract driver profile ────────────────────────────────
    logger.info("[Part A] Extracting driver profile directly from Sample Conversation sheet...")
    try:
        profile = extract_driver_profile(str(workbook_path))
    except Exception as e:
        logger.exception(f"Error during Part A (driver profile extraction): {e}")
        sys.exit(1)

    logger.info("Extracted driver profile successfully:")
    for key, value in profile.items():
        logger.info(f"  {key:<25} {value}")

    # ── Part B: Filter and rank loads ─────────────────────────────────
    logger.info("[Part B] Loading and filtering/ranking loads...")
    try:
        loads_df = load_loads(str(workbook_path))
        ranking = rank_loads(loads_df, profile)
    except Exception as e:
        logger.exception(f"Error during Part B (load ranking): {e}")
        sys.exit(1)

    logger.info("Top 3 eligible loads:")
    for i, load in enumerate(ranking["top3"], 1):
        logger.info(
            f"  #{i}  {load['load_id']}  "
            f"{load['origin']} -> {load['destination']}  "
            f"${load['effective_rate_per_mile']:.3f}/mi  "
            f"(price ${load['price_usd']:,.0f}, "
            f"total {load['total_miles']:.1f} mi)"
        )

    if ranking["rejected"]:
        logger.info("Rejected / skipped loads:")
        for r in ranking["rejected"]:
            logger.info(f"  {r['load_id']}: {r['reason']}")

    # ── Write output ───────────────────────────────────────────────────
    output = {
        "driver_profile": profile,
        "ranking": ranking,
    }
    out_path = OUTPUT_DIR / "results.json"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Results successfully written to {out_path}")
    except Exception as e:
        logger.error(f"Failed to write results to {out_path}: {e}")
        sys.exit(1)

    logger.info("=" * 60)


if __name__ == "__main__":
    main()

