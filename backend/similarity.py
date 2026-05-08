import torch
import torch.nn.functional as F
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import config

_model = None


def get_model():
    global _model
    if _model is None:
        device = config.BGE_DEVICE
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        _model = SentenceTransformer(config.BGE_MODEL_NAME, device=device)
        if config.BGE_USE_FP16 and device == "cuda":
            _model.half()
    return _model


# ═══════════════════════════════════════════════════════
# 相似度引擎 — 工厂模式
# ═══════════════════════════════════════════════════════

class BaseSimilarityEngine:
    def compute(self, word1: str, word2: str) -> float:
        raise NotImplementedError


class BGEEngine(BaseSimilarityEngine):
    """BGE 句子级编码：将两个词独立编码为句向量，计算余弦相似度"""

    def compute(self, word1: str, word2: str) -> float:
        model = get_model()
        prefix = config.BGE_INSTRUCTION_PREFIX
        texts = [prefix + word1, prefix + word2]
        embeddings = model.encode(texts, convert_to_tensor=True)
        emb1 = embeddings[0].cpu().numpy().reshape(1, -1)
        emb2 = embeddings[1].cpu().numpy().reshape(1, -1)
        sim = cosine_similarity(emb1, emb2)[0][0]
        return round(float(sim) * 100, config.SIMILARITY_DECIMAL)


class BGEScipyEngine(BaseSimilarityEngine):
    """
    BGE 语义向量化 + SciPy 高精度统计校准引擎

    1. 用 BGE 模型将词库中所有词编码为向量
    2. 随机采样词对，用 scipy 计算基线分布（μ, σ）
    3. 查询时计算余弦相似度的 z-score，经 sigmoid 映射到 [0, 100]

    效果：无关词对（接近基线均值）分数被压缩到低位，
          同义词对（远高于基线）分数被放大到高位。
    """

    def __init__(self):
        self._baseline_mean = None
        self._baseline_std = None

    def _calibrate(self):
        import word_bank
        from scipy.spatial.distance import pdist

        model = get_model()
        words = word_bank.load_words()
        n = len(words)

        if n < 10:
            self._baseline_mean = 0.5
            self._baseline_std = 0.15
            return

        # 编码所有词库词汇
        prefix = config.BGE_INSTRUCTION_PREFIX
        texts = [prefix + w for w in words]
        embeddings = model.encode(texts, convert_to_tensor=True).cpu().numpy()

        # 用 scipy 一次性计算所有词对的余弦距离（高精度批量计算）
        # pdist 返回压缩距离矩阵，metric='cosine' 即 1 - cos_sim
        distances = pdist(embeddings, metric="cosine")
        similarities = 1.0 - distances

        self._baseline_mean = float(np.mean(similarities))
        self._baseline_std = float(np.std(similarities))

        # 防止 std 过小导致 z-score 爆炸
        if self._baseline_std < 0.01:
            self._baseline_std = 0.01

    def compute(self, word1: str, word2: str) -> float:
        if self._baseline_mean is None:
            self._calibrate()

        model = get_model()
        prefix = config.BGE_INSTRUCTION_PREFIX
        texts = [prefix + word1, prefix + word2]
        embeddings = model.encode(texts, convert_to_tensor=True).cpu().numpy()

        # SciPy 高精度余弦距离
        from scipy.spatial.distance import cosine
        from scipy.special import expit

        cos_dist = cosine(embeddings[0], embeddings[1])
        cos_sim = 1.0 - cos_dist

        # z-score: 相对基线的偏离程度
        z = (cos_sim - self._baseline_mean) / self._baseline_std

        # sigmoid 映射: 中心偏移 + 陡峭度控制
        center = config.SIMILARITY_SIGMOID_CENTER
        steepness = config.SIMILARITY_SIGMOID_STEEPNESS
        calibrated = expit((z - center) * steepness)

        return round(float(calibrated) * 100, config.SIMILARITY_DECIMAL)


class WMDEngine(BaseSimilarityEngine):
    """
    WMD（Word Mover's Distance）字符级最优匹配引擎

    将中文词语拆解为字符（token），获取每个字符在上下文中的向量表示，
    再用匈牙利算法找到两组字符向量的最优匹配，以匹配对的平均余弦
    相似度作为两个词语的相似度。

    优势：对短词语（2-4字）能捕捉到字符级别的语义关联，避免 BGE
          句向量过度依赖字面重叠的问题。
    """

    def compute(self, word1: str, word2: str) -> float:
        model = get_model()
        tokenizer = model.tokenizer
        device = model.device

        embeds1 = self._token_embeddings(word1, model, tokenizer, device)
        embeds2 = self._token_embeddings(word2, model, tokenizer, device)

        if embeds1 is None or embeds2 is None:
            return config.WORD_NOT_IN_BANK_VALUE

        # L2 归一化，使内积等价于余弦相似度
        embeds1 = F.normalize(embeds1, p=2, dim=1)
        embeds2 = F.normalize(embeds2, p=2, dim=1)

        sim_matrix = (embeds1 @ embeds2.T).cpu().numpy()
        dist_matrix = 1.0 - sim_matrix

        n1, n2 = sim_matrix.shape
        n = max(n1, n2)

        # 距离矩阵补齐为方阵（用 1.0 = 最大余弦距离填充）
        padded_dist = np.ones((n, n))
        padded_dist[:n1, :n2] = dist_matrix

        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(padded_dist)

        # 仅计入真实 token 间的匹配对
        real_mask = (row_ind < n1) & (col_ind < n2)
        if real_mask.sum() == 0:
            return 0.0

        avg_sim = sim_matrix[row_ind[real_mask], col_ind[real_mask]].mean()
        return round(float(avg_sim) * 100, config.SIMILARITY_DECIMAL)

    def _token_embeddings(self, word, model, tokenizer, device):
        encoded = tokenizer(word, return_tensors="pt")
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded["attention_mask"].to(device)

        # 获取底层 Transformer（跳过 Pooling / Normalize 层）
        transformer = model[0].auto_model

        with torch.no_grad():
            outputs = transformer(input_ids=input_ids, attention_mask=attention_mask)

        # 去掉 [CLS] 和 [SEP]，仅保留实际 token
        token_embeds = outputs.last_hidden_state[0, 1:-1]
        if token_embeds.shape[0] == 0:
            return None
        return token_embeds


# ═══════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════

_engine = None
_engine_type = None


def get_engine() -> BaseSimilarityEngine:
    global _engine, _engine_type
    engine_type = config.SIMILARITY_ENGINE
    if _engine is None or _engine_type != engine_type:
        if engine_type == "bge":
            _engine = BGEEngine()
        elif engine_type == "bge_scipy":
            _engine = BGEScipyEngine()
        elif engine_type == "wmd":
            _engine = WMDEngine()
        else:
            raise ValueError(f"未知的相似度引擎类型: {engine_type}")
        _engine_type = engine_type
    return _engine


# ═══════════════════════════════════════════════════════
# 对外统一接口（保持向后兼容）
# ═══════════════════════════════════════════════════════

def compute_similarity(word1: str, word2: str) -> float:
    raw = get_engine().compute(word1, word2)
    power = config.SIMILARITY_POWER
    if power != 1.0:
        return round((raw / 100.0) ** power * 100.0, config.SIMILARITY_DECIMAL)
    return raw
