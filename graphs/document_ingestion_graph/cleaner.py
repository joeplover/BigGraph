import re


class TextCleaner:
    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = self._normalize_newlines(text)
        text = self._remove_invisible_chars(text)
        text = self._collapse_spaces(text)
        text = self._merge_broken_chinese_lines(text)
        text = self._collapse_blank_lines(text)
        return text.strip()

    def _normalize_newlines(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _remove_invisible_chars(self, text: str) -> str:
        return re.sub(r"[​-‏﻿]", "", text)

    def _collapse_spaces(self, text: str) -> str:
        return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())

    def _merge_broken_chinese_lines(self, text: str) -> str:
        lines = text.splitlines()
        merged: list[str] = []
        for line in lines:
            if not merged:
                merged.append(line)
                continue
            prev = merged[-1]
            if self._should_merge(prev, line):
                merged[-1] = prev + line
            else:
                merged.append(line)
        return "\n".join(merged)

    def _should_merge(self, prev: str, current: str) -> bool:
        if not prev or not current:
            return False
        if prev.startswith(("#", "|", "- ", "* ", ">", "```")) or current.startswith(("#", "|", "- ", "* ", ">", "```")):
            return False
        if prev.endswith(("。", "！", "？", "：", "；", ".", "!", "?", ":", ";", "…")):
            return False
        if not re.search(r"[一-鿿]$", prev):
            return False
        if not re.search(r"^[一-鿿]", current):
            return False
        return True

    def _collapse_blank_lines(self, text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)
