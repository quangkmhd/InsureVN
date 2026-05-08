"""Corpus-level Markdown heading analysis for chunking decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.eval.models import CorpusDocument, JsonDict

HEADING_PATTERN = re.compile(r"^(#{1,4})\s+")


@dataclass(frozen=True)
class HeadingLevelRecommendation:
    """Statistics and recommendation for one Markdown heading level."""

    level: int
    count: int
    avg_chars_after: float
    recommendation: str

    def to_payload(self) -> JsonDict:
        """Return a JSON-ready payload."""

        return {
            "level": self.level,
            "count": self.count,
            "avg_chars_after": self.avg_chars_after,
            "recommendation": self.recommendation,
        }


@dataclass
class HeadingLevelAccumulator:
    """Mutable accumulator for one heading level."""

    count: int = 0
    chars_after: list[int] = field(default_factory=list)


def analyze_heading_structure(
    documents: list[CorpusDocument],
) -> dict[int, HeadingLevelRecommendation]:
    """Analyze heading density across the loaded Markdown corpus."""

    accumulators: dict[int, HeadingLevelAccumulator] = {}
    for document in documents:
        lines = document.text.splitlines()
        heading_positions: list[tuple[int, int]] = []
        for line_index, line in enumerate(lines):
            match = HEADING_PATTERN.match(line)
            if match is None:
                continue
            level = len(match.group(1))
            heading_positions.append((line_index, level))

        for heading_index, (line_index, level) in enumerate(heading_positions):
            next_line_index = (
                heading_positions[heading_index + 1][0]
                if heading_index + 1 < len(heading_positions)
                else len(lines)
            )
            section_chars = sum(
                len(lines[index]) for index in range(line_index, next_line_index)
            )
            accumulator = accumulators.setdefault(level, HeadingLevelAccumulator())
            accumulator.count += 1
            accumulator.chars_after.append(section_chars)

    recommendations: dict[int, HeadingLevelRecommendation] = {}
    for level, accumulator in sorted(accumulators.items()):
        avg_chars_after = sum(accumulator.chars_after) / len(accumulator.chars_after)
        recommendations[level] = HeadingLevelRecommendation(
            level=level,
            count=accumulator.count,
            avg_chars_after=avg_chars_after,
            recommendation=recommend_heading_level(avg_chars_after),
        )
    return recommendations


def recommend_heading_level(avg_chars_after: float) -> str:
    """Return a recommendation label for an average section size."""

    if avg_chars_after < 500:
        return "too_small_do_not_cut"
    if avg_chars_after < 1500:
        return "small_cut_then_merge"
    if avg_chars_after <= 6000:
        return "ideal_cut_here"
    return "large_cut_deeper"


def decide_cut_level(
    recommendations: dict[int, HeadingLevelRecommendation],
) -> int:
    """Choose the best Markdown heading level for section chunking."""

    if not recommendations:
        return 2
    ideal_levels = {
        level: recommendation
        for level, recommendation in recommendations.items()
        if 1500 <= recommendation.avg_chars_after <= 6000
    }
    if ideal_levels:
        return min(ideal_levels)
    return min(
        recommendations,
        key=lambda level: abs(recommendations[level].avg_chars_after - 3000),
    )


def heading_analysis_payload(
    recommendations: dict[int, HeadingLevelRecommendation],
) -> list[JsonDict]:
    """Return heading recommendations as sorted JSON-ready payloads."""

    return [
        recommendation.to_payload()
        for _, recommendation in sorted(recommendations.items())
    ]
