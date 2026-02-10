"""Output summarization for voice feedback."""

import re
from dataclasses import dataclass

from .config import SummaryConfig


@dataclass
class Summary:
    """A summarized output."""

    text: str
    has_error: bool
    has_question: bool
    is_complete: bool
    raw_length: int


class OutputSummarizer:
    """Summarizes terminal output for voice feedback."""

    # Patterns to detect various output types
    ERROR_PATTERNS = [
        r"error:",
        r"Error:",
        r"ERROR",
        r"failed",
        r"Failed",
        r"FAILED",
        r"exception",
        r"Exception",
        r"traceback",
        r"Traceback",
        r"panic:",
        r"PANIC",
        r"fatal:",
        r"Fatal:",
    ]

    QUESTION_PATTERNS = [
        r"\?\s*$",  # Ends with question mark
        r"Do you want",
        r"Would you like",
        r"Should I",
        r"Shall I",
        r"Please confirm",
        r"Enter .* to continue",
        r"\[y/n\]",
        r"\[Y/n\]",
        r"\[yes/no\]",
    ]

    COMPLETION_PATTERNS = [
        r"Done\.?$",
        r"Complete\.?$",
        r"Finished\.?$",
        r"Successfully",
        r"Created .+\.",
        r"Updated .+\.",
        r"Fixed .+\.",
        r"> $",  # Claude Code prompt
    ]

    # Patterns to extract key information
    FILE_PATTERN = r"(?:(?:Created|Modified|Updated|Edited|Deleted|Reading|Writing)\s+)?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)"
    COUNT_PATTERN = r"(\d+)\s+(?:files?|changes?|errors?|warnings?|tests?|passed|failed)"

    def __init__(self, config: SummaryConfig):
        self.config = config

    def summarize(self, text: str) -> Summary:
        """Summarize terminal output for voice feedback."""
        if not text:
            return Summary(
                text="No output",
                has_error=False,
                has_question=False,
                is_complete=True,
                raw_length=0,
            )

        # Detect characteristics
        has_error = self._has_error(text)
        has_question = self._has_question(text)
        is_complete = self._is_complete(text)

        # Generate summary based on strategy
        if self.config.strategy == "full":
            summary_text = self._truncate_to_words(text, self.config.max_spoken_length)
        elif self.config.strategy == "first_last":
            summary_text = self._first_last_summary(text)
        else:  # smart
            summary_text = self._smart_summary(text, has_error, has_question, is_complete)

        return Summary(
            text=summary_text,
            has_error=has_error,
            has_question=has_question,
            is_complete=is_complete,
            raw_length=len(text),
        )

    def _has_error(self, text: str) -> bool:
        """Check if output contains errors."""
        text_lower = text.lower()
        return any(re.search(p, text, re.IGNORECASE) for p in self.ERROR_PATTERNS)

    def _has_question(self, text: str) -> bool:
        """Check if output contains a question."""
        return any(re.search(p, text, re.IGNORECASE | re.MULTILINE) for p in self.QUESTION_PATTERNS)

    def _is_complete(self, text: str) -> bool:
        """Check if output indicates completion."""
        lines = text.strip().split("\n")
        if not lines:
            return False
        last_lines = "\n".join(lines[-3:])
        return any(re.search(p, last_lines, re.IGNORECASE) for p in self.COMPLETION_PATTERNS)

    def _truncate_to_words(self, text: str, max_words: int) -> str:
        """Truncate text to a maximum number of words."""
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    def _first_last_summary(self, text: str) -> str:
        """Create summary from first and last lines."""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) <= 4:
            return " ".join(lines)

        first_lines = lines[:2]
        last_lines = lines[-2:]
        middle_count = len(lines) - 4

        summary = " ".join(first_lines)
        summary += f" ... {middle_count} more lines ... "
        summary += " ".join(last_lines)

        return self._truncate_to_words(summary, self.config.max_spoken_length)

    def _smart_summary(self, text: str, has_error: bool, has_question: bool, is_complete: bool) -> str:
        """Create an intelligent summary extracting key information."""
        parts = []

        # Start with status
        if has_error:
            parts.append("Error encountered.")
            # Extract error message
            error_msg = self._extract_error_message(text)
            if error_msg:
                parts.append(error_msg)
        elif has_question:
            parts.append("Question from Claude:")
            # Extract the question
            question = self._extract_question(text)
            if question:
                parts.append(question)
        elif is_complete:
            parts.append("Complete.")

        # Extract key actions
        actions = self._extract_actions(text)
        if actions:
            parts.extend(actions[:3])  # Limit to 3 actions

        # Extract file information
        files = self._extract_files(text)
        if files:
            if len(files) == 1:
                parts.append(f"Modified {files[0]}.")
            elif len(files) <= 3:
                parts.append(f"Modified {', '.join(files)}.")
            else:
                parts.append(f"Modified {len(files)} files.")

        # Extract counts
        counts = self._extract_counts(text)
        if counts:
            parts.extend(counts[:2])

        # If nothing extracted, fall back to first_last
        if len(parts) <= 1:
            return self._first_last_summary(text)

        summary = " ".join(parts)
        return self._truncate_to_words(summary, self.config.max_spoken_length)

    def _extract_error_message(self, text: str) -> str | None:
        """Extract the main error message."""
        for pattern in self.ERROR_PATTERNS:
            match = re.search(f"{pattern}.*", text, re.IGNORECASE)
            if match:
                # Get the line containing the error
                line = match.group(0)
                # Clean and truncate
                line = re.sub(r"\s+", " ", line).strip()
                if len(line) > 100:
                    line = line[:100] + "..."
                return line
        return None

    def _extract_question(self, text: str) -> str | None:
        """Extract a question from the output."""
        lines = text.strip().split("\n")
        # Look for lines ending in ? or containing question patterns
        for line in reversed(lines[-10:]):  # Check last 10 lines
            line = line.strip()
            if line.endswith("?") or any(re.search(p, line, re.IGNORECASE) for p in self.QUESTION_PATTERNS):
                return line[:150] if len(line) > 150 else line
        return None

    def _extract_actions(self, text: str) -> list[str]:
        """Extract action statements from output."""
        action_patterns = [
            r"(Created .+?\.)",
            r"(Updated .+?\.)",
            r"(Added .+?\.)",
            r"(Removed .+?\.)",
            r"(Fixed .+?\.)",
            r"(Installed .+?\.)",
            r"(Running .+?\.)",
            r"(Building .+?\.)",
        ]

        actions = []
        for pattern in action_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            actions.extend(matches)

        return actions

    def _extract_files(self, text: str) -> list[str]:
        """Extract mentioned file names."""
        files = re.findall(self.FILE_PATTERN, text)
        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in files:
            if f not in seen and not f.startswith("."):
                seen.add(f)
                unique_files.append(f)
        return unique_files

    def _extract_counts(self, text: str) -> list[str]:
        """Extract count information."""
        matches = re.findall(self.COUNT_PATTERN, text, re.IGNORECASE)
        return [f"{m[0]} {m[1]}" if isinstance(m, tuple) else m for m in matches[:3]]


def summarize_for_voice(text: str, config: SummaryConfig) -> str:
    """Convenience function to summarize text for voice output."""
    summarizer = OutputSummarizer(config)
    summary = summarizer.summarize(text)
    return summary.text
