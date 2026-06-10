from pathlib import Path
import jieba


class ChineseTokenizer:
    def __init__(self, user_dict_path: str | None = None, stopwords_path: str | None = None) -> None:
        if user_dict_path and Path(user_dict_path).exists():
            jieba.load_userdict(user_dict_path)
        self._stopwords = self._load_stopwords(stopwords_path)

    def cut(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return [w.strip() for w in jieba.lcut(text) if w.strip() and w.strip() not in self._stopwords]

    def keywords(self, text: str, limit: int = 20) -> list[str]:
        if not text or not text.strip():
            return []
        freq: dict[str, int] = {}
        for w in self.cut(text):
            if len(w) >= 2:
                freq[w] = freq.get(w, 0) + 1
        return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:limit]]

    def _load_stopwords(self, path: str | None) -> set[str]:
        if path and Path(path).exists():
            return {l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()}
        return {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些", "之", "与", "及", "或", "但", "而", "被", "把", "对", "从", "以", "让", "为", "所", "得", "地", "等", "并", "中", "外", "里", "时", "后", "前", "其", "某"}
