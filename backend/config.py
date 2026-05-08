BGE_MODEL_NAME = "BAAI/bge-base-zh-v1.5"
BGE_DEVICE = "auto"
BGE_USE_FP16 = True

# ── 相似度引擎切换 ──
# "bge"       — BGE 句子级编码 + 原始余弦相似度
# "bge_scipy" — BGE 语义向量化 + SciPy 高精度统计校准（推荐）
# "wmd"       — 字符级最优匹配（Word Mover's Distance）
SIMILARITY_ENGINE = "bge_scipy"

# ── SciPy 校准参数（仅 bge_scipy 引擎生效）──
# sigmoid 中心偏移: z-score 阈值，越高越严格（无关词分数越低）
#   2.5 = 词对需高于基线 2.5σ 才能拿到 50%
SIMILARITY_SIGMOID_CENTER = 2.5
# sigmoid 陡峭度: 越高过渡越尖锐，越低过渡越平缓
SIMILARITY_SIGMOID_STEEPNESS = 0.8

# ── 幂律重校准（仅 bge / wmd 引擎生效）──
SIMILARITY_POWER = 1.0

# BGE模型的指令前缀，用于增强短文本（如单个中文词语）的语义编码质量
# 仅在 SIMILARITY_ENGINE = "bge" 时生效
# 对短文本添加前缀可帮助模型更好理解编码任务，提升相似度计算的合理性
# 设为空字符串 "" 可禁用前缀
BGE_INSTRUCTION_PREFIX = "为这个句子生成表示以用于检索相关文章："
ACCUMULATE_CORRECT_WORDS = True
SIMILARITY_DECIMAL = 4
WORD_NOT_IN_BANK_VALUE = 0.0
AUTO_NEW_ROUND_ON_CORRECT = True
WORD_BANK_FILE = "words.json"
AVOID_REPEAT_TARGET = True
