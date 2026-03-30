import argparse
import json
import os
import random
import logging
import time
from datetime import datetime

import yaml

from modules.trend_researcher import TrendResearcher
from modules.content_generator import ContentGenerator
from modules.blogger_uploader import BloggerUploader

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config: dict, base_dir: str = "."):
        self.config = config
        self.base_dir = base_dir
        self.schedule = config["schedule"]

    def posts_this_week(self) -> int:
        log_dir = os.path.join(self.base_dir, "logs")
        if not os.path.exists(log_dir):
            return 0

        today = datetime.now()
        weekday = today.weekday()
        count = 0

        for f in os.listdir(log_dir):
            if f.endswith(".log"):
                try:
                    log_date = datetime.strptime(f.replace(".log", ""), "%Y-%m-%d")
                    days_diff = (today - log_date).days
                    if days_diff <= weekday:
                        log_path = os.path.join(log_dir, f)
                        with open(log_path) as lf:
                            if "Published:" in lf.read():
                                count += 1
                except ValueError:
                    continue
        return count

    def should_post_today(self) -> bool:
        current_count = self.posts_this_week()
        max_posts = self.schedule["posts_per_week"][1]

        if current_count >= max_posts:
            logger.info(f"Already posted {current_count} times this week (max {max_posts}). Skipping.")
            return False

        today = datetime.now()
        weekday = today.weekday()
        remaining_days = 7 - weekday
        min_posts = self.schedule["posts_per_week"][0]
        needed = max(0, min_posts - current_count)

        if remaining_days <= 0:
            return False

        probability = max(needed / remaining_days, 0.5)
        probability = min(probability, 1.0)

        roll = random.random()
        should_post = roll < probability
        logger.info(
            f"Post decision: count={current_count}, needed={needed}, "
            f"remaining_days={remaining_days}, prob={probability:.2f}, "
            f"roll={roll:.2f}, post={should_post}"
        )
        return should_post

    def run_pipeline(self) -> bool:
        date_str = datetime.now().strftime("%Y-%m-%d")

        logger.info("=== Step 1: Trend Research ===")
        researcher = TrendResearcher(
            config=self.config,
            output_dir=os.path.join(self.base_dir, "output", "keywords"),
            posted_keywords_path=os.path.join(self.base_dir, "data", "posted_keywords.json"),
        )
        keywords_path = researcher.run()

        with open(keywords_path) as f:
            keywords = json.load(f)

        if not keywords:
            logger.warning("No keywords found. Skipping.")
            return False

        keyword_data = keywords[0]
        logger.info(f"Selected keyword: {keyword_data['keyword']}")

        logger.info("=== Step 2: Content Generation ===")
        generator = ContentGenerator(
            config=self.config,
            prompts_dir=os.path.join(self.base_dir, "prompts"),
            output_dir=os.path.join(self.base_dir, "output", "drafts"),
        )
        draft_path = generator.generate(keyword_data, date_str)

        if draft_path is None:
            logger.error("Content generation failed. Skipping upload.")
            return False

        logger.info("=== Step 3: Blogger Upload ===")
        uploader = BloggerUploader(
            config=self.config,
            posted_keywords_path=os.path.join(self.base_dir, "data", "posted_keywords.json"),
        )
        category = keyword_data.get("category", "")
        template = keyword_data.get("template", "")
        related = keyword_data.get("related_queries", [])

        # Base labels
        labels = ["AI", "artificial intelligence"]

        # Category label
        if category:
            labels.append(category)

        # Template-based labels
        template_labels = {
            "howto_apply": "how to",
            "best_tools": "best tools",
            "daily_ai_tips": "tips",
        }
        if template in template_labels:
            labels.append(template_labels[template])

        # Keyword as label (e.g. "AI home" → "AI home")
        labels.append(keyword_data["keyword"])

        # Compound label (e.g. "AI home tips")
        labels.append(f"AI {category} tips")

        # Top related queries as labels (max 3)
        for rq in related[:3]:
            labels.append(rq)

        # Deduplicate, filter empty
        labels = list(dict.fromkeys(l.strip() for l in labels if l.strip()))
        result = uploader.upload(draft_path, keyword_data, labels)

        logger.info(f"Published: {result.get('url', 'unknown')}")
        return True

    def run(self, force: bool = False):
        logger.info("=== Auto Blog Orchestrator Started ===")

        if not force:
            delay_max = self.schedule.get("random_delay_max_hours", 0)
            if delay_max > 0:
                delay_seconds = random.uniform(0, delay_max * 3600)
                logger.info(f"Random delay: {delay_seconds / 60:.1f} minutes")
                time.sleep(delay_seconds)

            if not self.should_post_today():
                logger.info("Decided not to post today. Exiting.")
                return
        else:
            logger.info("Force mode: skipping schedule check and delay")

        try:
            self.run_pipeline()
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)

        logger.info("=== Orchestrator Finished ===")


def main():
    os.makedirs("logs", exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join("logs", f"{datetime.now().strftime('%Y-%m-%d')}.log")
            ),
        ],
    )

    parser = argparse.ArgumentParser(description="Auto Blog Generator")
    parser.add_argument("--now", action="store_true", help="Run immediately, skip schedule check and delay")
    args = parser.parse_args()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    orch = Orchestrator(config=config, base_dir=".")
    orch.run(force=args.now)


if __name__ == "__main__":
    main()
