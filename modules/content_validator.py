import os
import re
import subprocess
import logging
from statistics import stdev

logger = logging.getLogger(__name__)

BANNED_PHRASES = [
    "in today's rapidly evolving",
    "in today's world",
    "in today's digital age",
    "in today's fast-paced",
    "it's worth noting",
    "it is worth noting",
    "let's dive in",
    "let's dive into",
    "let's explore",
    "without further ado",
    "in this article, we will",
    "in this blog post",
    "have you ever wondered",
    "are you looking for",
    "look no further",
    "in conclusion",
    "to sum up",
    "to summarize",
    "as we've seen",
    "as mentioned earlier",
    "it goes without saying",
    "needless to say",
    "at the end of the day",
    "when it comes to",
    "on the other hand",
    "in the ever-changing",
    "the world of",
    "navigating the world",
    "dive deeper into",
    "a game-changer",
    "revolutionize",
    "leverage the power",
    "harness the power",
    "unlock the potential",
    "empower you to",
    "streamline your",
    "take it to the next level",
    "the possibilities are endless",
    "in the realm of",
]


class ContentValidator:
    def __init__(self, config: dict, prompts_dir: str):
        self.config = config
        self.prompts_dir = prompts_dir
        claude_config = config["claude"]
        self.claude_path = claude_config.get("path", "claude")
        self.claude_timeout = claude_config.get("timeout_seconds", 120)
        validator_config = config.get("validator", {})
        self.max_fix_attempts = validator_config.get("max_fix_attempts", 2)
        self.enabled = validator_config.get("enabled", True)

    def _check_ai_patterns(self, text: str) -> list[str]:
        issues = []
        text_lower = text.lower()

        # 1. Banned phrases
        for phrase in BANNED_PHRASES:
            if phrase in text_lower:
                issues.append(f"Banned phrase found: \"{phrase}\"")

        # 2. Paragraph length uniformity
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        # Only check if there are enough paragraphs
        if len(paragraphs) >= 4:
            word_counts = [len(p.split()) for p in paragraphs]
            mean_wc = sum(word_counts) / len(word_counts)
            if mean_wc > 0:
                sd = stdev(word_counts) if len(word_counts) > 1 else 0
                cv = sd / mean_wc  # coefficient of variation
                if cv < 0.2:
                    issues.append(
                        f"Uniform paragraph lengths (CV={cv:.2f}). "
                        "Vary paragraph sizes for a natural feel."
                    )

        # 3. Repetitive sentence openers
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) >= 4:
            openers = [s.split()[0].lower() for s in sentences if s.split()]
            for i in range(len(openers) - 2):
                if openers[i] == openers[i + 1] == openers[i + 2]:
                    issues.append(
                        f"Repetitive sentence opener: \"{openers[i]}\" "
                        "used 3+ times consecutively."
                    )
                    break

        return issues
