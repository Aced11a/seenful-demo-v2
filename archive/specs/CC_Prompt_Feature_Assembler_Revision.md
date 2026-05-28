# Claude Code 提示词 · L2 Feature Assembler 需求修正

## 背景说明（必读）

你之前看到的 L2 Association Engine 工程规范 v1.3.1 中,§3.2.1 (location_score) / §3.2.2 (time_score) / §3.2.3 (theme_overlap_score) 的实现方案**已被废弃**。

下面是替代方案。**在你开始任何 Feature Assembler 代码实现之前,先把这三个维度的新需求理解清楚,并按这份新方案更新 `docs/07_dimension_thresholds.md` 和相关代码契约。**

不要按 v1.3.1 老方案实现。

---

## 任务

按下面三条新方案,做以下事情:

1. **更新 `docs/07_dimension_thresholds.md`**:把 §3.2.1 / §3.2.2 / §3.2.3 三段重写
2. **创建 `decisions/0004-feature-assembler-revision.md` ADR**:记录这次方案替换的理由
3. **更新 `src/contracts/features.py`**:补充新方案需要的新字段(见下方"契约变更")
4. **暂时不实现代码,只产出文档 + 契约**。代码实现等我下一轮指令

---

## 新方案 1 · location_score(替换原 §3.2.1)

### 原方案的问题

老方案只用固定的 GPS 距离阈值(<200m → 1.0, <500m → 0.8, <2000m → 0.5),不区分用户所在城市。结果:

- 用户在常驻城市内 1km 距离会判 medium,但产品语义上 1km 是"两个不同区域",不该并入
- 用户在外国旅游时,500m 跨度可能是同一景区,但同样阈值会把同一景区判散

### 新方案

引入**地理上下文感知**:同一个 GPS 距离,在常驻城市要求更严,在外地放宽。

**实现要点**:

```
1. 判断每张照片的"地理上下文":
   - 是否在用户常驻城市(home_city) 范围内
   - 若不在,是否跨省 / 跨国

2. 根据上下文选择阈值表:
   - home_city: 强 < 100m / 中 < 300m / 弱 < 800m
   - cross_province: 强 < 500m / 中 < 1500m / 弱 < 5000m
   - cross_country: 强 < 2000m / 中 < 5000m / 弱 < 15000m

3. 计算用户常驻城市:
   - 30 天内 GPS 上传频次最高的行政区(到市级)
   - 缓存为 user_profile.home_city
   - 兜底:若数据不足,默认按 home_city 表处理(保守策略)

4. 跨上下文混合的情况:
   - 一组照片中既有 home_city 也有 cross_province → 取最严的表(home_city)
   - 这是反例兜底:防止"刚好出市又回市"的误聚合
```

### 契约变更

`src/contracts/features.py` 的 `LocationFeature` 新增字段:

```python
class LocationContext(str, Enum):
    HOME_CITY = "home_city"
    CROSS_PROVINCE = "cross_province"
    CROSS_COUNTRY = "cross_country"
    MIXED = "mixed"   # 一组照片跨上下文
    UNKNOWN = "unknown"

class LocationFeature(BaseModel):
    score: float
    confidence: float
    max_distance_m: float
    is_high_frequency_place: bool
    context: LocationContext        # ★ 新增
    threshold_table_used: str       # ★ 新增,落痕用("home_city" / "cross_province" / ...)
    primary_signal: str
```

### 阈值配置(写入 `config/dimension_thresholds.yaml`)

```yaml
location_distance_thresholds:
  home_city:
    strong_m: 100
    medium_m: 300
    weak_m: 800
  cross_province:
    strong_m: 500
    medium_m: 1500
    weak_m: 5000
  cross_country:
    strong_m: 2000
    medium_m: 5000
    weak_m: 15000

home_city_detection:
  lookback_days: 30
  min_uploads_required: 10
  fallback_context: "home_city"
```

---

## 新方案 2 · time_score(替换原 §3.2.2)

### 原方案的问题

老方案只看照片组首尾时间跨度,忽略中间分布。结果有两类失败:

**失败 1**:同日两件事被错连
- 9 点拍早餐 → 12 点拍午餐 → 18 点拍晚餐
- 跨度 9 小时,落在"< 12h → 0.7"档,但产品语义上这是**三个独立事件**

**失败 2**:多日旅游被判散
- Day1 上午景点 → Day2 中午景点 → Day3 下午景点
- 跨度 ~50h,落在"> 48h → 0.2"档,但产品语义上这是**一段连续旅行**

### 新方案

**问题 1 解法 · 双峰检测**:用照片间隔的中位数判断分布密度。

```python
# 伪代码,文档里写清楚

gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
median_gap = statistics.median(gaps)
time_span = max(timestamps) - min(timestamps)

# 双峰判定: 中位间隔 > 总跨度的 30% 且 ≥ 4 张照片
is_bimodal = (median_gap > time_span * 0.3) and len(photos) >= 4

if is_bimodal:
    # 视为两次独立活动,time_score 直接判为"弱"档,不参与强成集
    return {"score": 0.3, "is_bimodal": True}
```

**为什么 ≥ 4 张**:3 张照片只能形成 2 个 gap,统计意义不足。

**问题 2 解法 · 旅游放宽**:GPS 提示在外地时,时间窗口扩大。

```python
# 复用 location_score 的 context 字段
location_context = features.location.context

if location_context in ("cross_province", "cross_country"):
    # 外地旅游,时间窗放宽: 跨度 < 72h 仍判强,跨度 < 168h(一周)判中
    if time_span_hours < 72:
        base_score = 1.0
    elif time_span_hours < 168:
        base_score = 0.85
    elif time_span_hours < 336:  # 两周
        base_score = 0.6
    else:
        base_score = 0.3
else:
    # 常驻城市,保留老方案分档
    if time_span_hours < 0.5:
        base_score = 1.0
    elif time_span_hours < 2:
        base_score = 0.9
    elif time_span_hours < 12:
        base_score = 0.7
    elif time_span_hours < 48:
        base_score = 0.5
    else:
        base_score = 0.2
```

### 契约变更

`src/contracts/features.py` 的 `TimeFeature` 新增字段:

```python
class TimeFeature(BaseModel):
    score: float
    confidence: float
    time_span_hours: float
    median_gap_hours: float       # ★ 新增
    is_bimodal: bool              # ★ 新增,问题 1 检测
    is_travel_relaxed: bool       # ★ 新增,问题 2 是否启用旅游放宽
    all_fallback: bool
    primary_signal: str
```

### 阈值配置

```yaml
time_score:
  bimodal_detection:
    median_gap_ratio_threshold: 0.3   # 中位间隔 / 总跨度
    min_photos_for_bimodal: 4
    bimodal_score: 0.3                # 命中双峰后的固定分

  home_city_brackets:
    - { max_hours: 0.5,   score: 1.0 }
    - { max_hours: 2,     score: 0.9 }
    - { max_hours: 12,    score: 0.7 }
    - { max_hours: 48,    score: 0.5 }
    - { max_hours: null,  score: 0.2 }

  travel_brackets:
    - { max_hours: 72,    score: 1.0 }
    - { max_hours: 168,   score: 0.85 }
    - { max_hours: 336,   score: 0.6 }
    - { max_hours: null,  score: 0.3 }

  fallback_confidence_multiplier: 0.5   # 全 upload_time_fallback 时
```

---

## 新方案 3 · theme_overlap_score(替换原 §3.2.3)

### 原方案的问题

老方案用 Jaccard 集合相交计算 theme_tags 重合度,**必须文字完全一致才算重合**。结果:

- `["夕阳"]` 和 `["晚霞"]` 重合度 = 0
- `["湖边"]` 和 `["水边"]` 重合度 = 0
- `["饭菜"]` 和 `["晚餐"]` 重合度 = 0

这种字面匹配丢失了大量语义相近的关联。

### 新方案

**用 embedding 余弦相似度替代 Jaccard**,具体做法:

```
1. 模型选择(任选其一,在 config 里可切换):
   - BGE-M3 (开源,中英文都强,推荐起步)
   - Qwen3-Embedding-0.6B (中文场景更贴 Qwen 生态)

2. 计算流程(双向最大池化):
   - 对每张照片的 theme_tags 列表,各 tag 单独 embed → 得到一组向量
   - 计算两两 tag 的余弦相似度矩阵
   - "双向最大池化": 对每个 A 中的 tag,取它在 B 中相似度最大的值;反过来对 B 中每个 tag 取它在 A 中最大值;两组取平均
   - 得到一个 0.0 - 1.0 的相似度分数

3. 转真值(分档):
   - cos ≥ 0.85 → strong (语义高度一致)
   - cos ≥ 0.70 → medium (语义相近)
   - cos ≥ 0.55 → light (有共同主题倾向)
   - cos <  0.55 → none
   ★ 这套阈值仍写入 dimension_thresholds.yaml,可热更新

4. 与 main_subjects / scene_type 的融合:
   - tag_embedding_score (新)   权重 0.6
   - main_subjects_jaccard (旧)  权重 0.3 (保留作为强证据)
   - scene_type_consistency (旧) 权重 0.1
```

### 双向最大池化的具体公式

```python
def bidirectional_max_pool_similarity(tags_a: list[str], tags_b: list[str]) -> float:
    """
    A = ["夕阳", "湖面"]  embed → [v_a1, v_a2]
    B = ["晚霞", "水边"]  embed → [v_b1, v_b2]

    相似度矩阵 S[i][j] = cos(v_ai, v_bj)
    例:
                晚霞    水边
        夕阳  [ 0.92    0.15 ]
        湖面  [ 0.18    0.88 ]

    A→B 方向: 对每行取 max → [0.92, 0.88] → mean = 0.90
    B→A 方向: 对每列取 max → [0.92, 0.88] → mean = 0.90
    最终: (0.90 + 0.90) / 2 = 0.90
    """
    if not tags_a or not tags_b:
        return 0.0
    sim_matrix = cosine_similarity_matrix(embed(tags_a), embed(tags_b))
    a_to_b = sim_matrix.max(axis=1).mean()
    b_to_a = sim_matrix.max(axis=0).mean()
    return (a_to_b + b_to_a) / 2.0
```

**为什么双向**:单向(只算 A→B 的平均最大)会被一方 tag 数量稀疏的情况骗。双向取平均更鲁棒。

### 契约变更

`src/contracts/features.py` 的 `ThemeFeature` 新增字段:

```python
class ThemeFeature(BaseModel):
    score: float                           # 综合分(融合后)
    tag_embedding_similarity: float        # ★ 新增,embedding 余弦
    main_subjects_jaccard: float           # 保留(旧的字面匹配)
    scene_type_consistency: bool           # 保留
    embedding_model_used: str              # ★ 新增,落痕用("BGE-M3" / "Qwen3-Embedding-0.6B")
```

### 阈值配置

```yaml
theme_overlap:
  embedding_model: "BGE-M3"   # 可切 "Qwen3-Embedding-0.6B"
  embedding_dim: 1024

  fusion_weights:
    tag_embedding: 0.6
    main_subjects_jaccard: 0.3
    scene_type_consistency: 0.1

  similarity_to_band:
    strong: 0.85
    medium: 0.70
    weak: 0.55
```

### 工程考量

embedding 调用频次高,需要:

1. **Tag 级别缓存**:同一个 tag 的 embedding 永久缓存(Redis / 本地 kv),tag 字符串作为 key
2. **批量调用**:一组照片的所有 tag 一次性 embed,不要逐 tag 调
3. **降级策略**:embedding 服务不可用时,降级到老 Jaccard 算法,在 decision_log 标记 `theme_score_degraded: true`

---

## 你(Claude Code)接到这份提示词后的标准动作

按这个顺序执行,**每完成一步告诉我,等我确认再下一步**:

### Step 1 · 更新规范文档

修改 `docs/07_dimension_thresholds.md`:
- 把原 §3.2.1 / §3.2.2 / §3.2.3 三节标记为"已废弃 (deprecated v1.3.1)"
- 在下方新增"§3.2.1 新版 / §3.2.2 新版 / §3.2.3 新版"三节,内容来自本提示词
- 在文档顶部 changelog 加一行:
  `v1.3.2 (2026-05-12): 替换 location_score / time_score / theme_overlap_score 实现方案 (Ace + KY 评审)`

### Step 2 · 创建 ADR

新建 `decisions/0004-feature-assembler-revision.md`,记录:
- 三条方案替换的背景(老方案的失败模式)
- 新方案核心机制(地理上下文 / 双峰检测 / embedding 双向池化)
- 评估的备选项和拒绝理由
- 影响范围(契约变更 + 配置新增)
- 决策时间和决策人

### Step 3 · 更新数据契约

修改 `src/contracts/features.py`,补充上述三处契约变更。**只改契约,先不改实现**。
跑一次 `pytest tests/unit/test_contracts.py` 确认契约本身可实例化。

### Step 4 · 更新配置文件

修改 `config/dimension_thresholds.yaml`,添加上述三段新配置。
**保留**原有的 `dimension_bands` 顶层结构(用于真值表分档),新增的是各维度计算细则。

### Step 5 · 同步更新 docs/12_open_questions.md

把这次新增的待决策项写进去,初步给出推荐方案:

- **OQ-NNN** · 用户 home_city 数据缺失时的默认上下文(推荐:home_city 保守策略)
- **OQ-NNN+1** · embedding 模型在生产环境的部署形态(本地 vs API,影响延迟和成本)
- **OQ-NNN+2** · embedding 缓存的失效策略(目前推荐永不失效,因为 tag 语义稳定)

### Step 6 · 暂停

不要动 `src/features/` 的实现代码。等我审完文档和契约,再下一轮指令实现。

---

## 验收标准

- [ ] `docs/07_dimension_thresholds.md` 老方案标记 deprecated,新方案完整
- [ ] `decisions/0004-feature-assembler-revision.md` 完整
- [ ] `src/contracts/features.py` 三个 Feature 类新增字段,pydantic 校验通过
- [ ] `config/dimension_thresholds.yaml` 三段新配置就位
- [ ] `docs/12_open_questions.md` 新增 3 条 OQ 条目
- [ ] **没有任何 `src/features/` 下的实现代码改动**

---

## 不要做的事

- ❌ 不要把老方案代码直接删掉(标记 deprecated 即可,保留追溯)
- ❌ 不要假设我已经接好 embedding 服务,只在 docs 和 config 里规划
- ❌ 不要为了"看起来好"重新发明算法(双峰检测就用中位数 + 30% 比例,不要换其他统计量)
- ❌ 不要跳过 ADR 直接改文档(决策需要追溯链)
- ❌ 不要主动实现 src/features/*.py,等我下一轮指令

完成后告诉我每一步的结果,我审完再继续。
