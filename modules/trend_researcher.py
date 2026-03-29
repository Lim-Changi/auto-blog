import json
import os
import time
import random
import logging
from datetime import datetime, timedelta

from pytrends.request import TrendReq

logger = logging.getLogger(__name__)


class TrendResearcher:
    def __init__(self, config: dict, output_dir: str, posted_keywords_path: str):
        self.config = config
        self.output_dir = output_dir
        self.posted_keywords_path = posted_keywords_path
        self.trends_config = config["trends"]
        self.categories = config["content"]["categories"]

    def build_queries(self) -> list[str]:
        return [f"AI {cat}" for cat in self.categories]

    def fetch_trends(self, queries: list[str]) -> list[dict]:
        pytrends = TrendReq(hl="en-US", tz=360)
        results = []

        for query in queries:
            time.sleep(random.uniform(2, 5))
            try:
                pytrends.build_payload(
                    [query],
                    timeframe=f"now {self.trends_config['lookback_days']}-d",
                    geo=self.trends_config["region"],
                )
                interest_df = pytrends.interest_over_time()
                if interest_df.empty:
                    continue

                interest = int(interest_df[query].mean())

                related = pytrends.related_queries()
                related_queries = []
                if query in related and related[query]["top"] is not None:
                    related_queries = related[query]["top"]["query"].tolist()[:5]

                results.append({
                    "keyword": query,
                    "interest": interest,
                    "result_count": len(related_queries) * 100 + 1,
                    "related_queries": related_queries,
                })
            except Exception as e:
                logger.warning(f"Failed to fetch trends for '{query}': {e}")
                continue

        return results

    def score_keywords(self, raw_data: list[dict]) -> list[dict]:
        with open(self.posted_keywords_path) as f:
            posted = json.load(f)

        scored = []
        for item in raw_data:
            if item["keyword"] in posted:
                continue
            interest = item["interest"]
            competition = item["result_count"]
            score = interest / (competition + 1)
            scored.append({**item, "score": round(score, 4)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def select_template(self, keyword: str) -> str:
        kw = keyword.lower()
        if kw.startswith("how to") or "how to" in kw:
            return "howto_apply"
        if kw.startswith("best") or "best" in kw or "top" in kw:
            return "best_tools"
        return "daily_ai_tips"

    def run(self) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        queries = self.build_queries()
        raw_data = self.fetch_trends(queries)
        scored = self.score_keywords(raw_data)

        max_kw = self.trends_config["max_keywords_per_run"]
        top_keywords = scored[:max_kw]

        for kw in top_keywords:
            kw["template"] = self.select_template(kw["keyword"])
            title_keyword = kw["keyword"].replace("AI ", "")
            if kw["template"] == "howto_apply":
                kw["title_suggestion"] = f"How to Use AI for {title_keyword.title()} — A Simple Guide for Beginners"
            elif kw["template"] == "best_tools":
                kw["title_suggestion"] = f"Best Free AI Tools for {title_keyword.title()} in 2026"
            else:
                kw["title_suggestion"] = f"5 Easy Ways AI Can Help You With {title_keyword.title()}"

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = os.path.join(self.output_dir, f"{date_str}.json")
        with open(output_path, "w") as f:
            json.dump(top_keywords, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(top_keywords)} keywords to {output_path}")
        return output_path
