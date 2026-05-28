# 16 · 路径 B Location 维度: 分级 DBSCAN + PCA OBB + 形状校正

> 路径 B (L2 主路径, **多张照片自身判定**) location 维度的算法规范.
> 算法依据: [ADR-0010](../decisions/0010-path-b-location-dbch-pca-shape.md).
> 仅覆盖路径 B. 路径 A (动态生长) location 维度走 DBCH 匹配, 见 [ADR-0005](../decisions/0005-place-anchor-dbch.md) + [docs/10 §二](./10_mini_album_schema.md).
>
> ⚠ **路径 A vs 路径 B location 算法对比**:
> - 路径 A: "1 张新 vs 1 本老相册 anchor" — **匹配**问题, 输出 MatchResult
> - 路径 B: "N 张新照片自身" — **聚类**问题, 输出 LocationFeature.band
> 二者共享 haversine / DBSCAN / 凸包工具函数, 但参数 + 判定逻辑完全不同 (路径 A eps 200~800m 细粒度, 路径 B eps 1500m 活动边界粒度).

---

## 一、变量定义

| 变量 | 定义 | 计算时机 |
|---|---|---|
| **K_outer** | DBSCAN(eps=1500m, min_samples=2) 簇数 (不含 outlier) | 任何时候 |
| **K_inner** | DBSCAN(eps=500m, min_samples=2) 簇数 | **仅 K_outer = 1** |
| **L** = outer_length_km | 外层那唯一簇 GPS 做 PCA, **主轴投影跨度** (km) | 仅 K_outer = 1 |
| **W** = outer_width_km | PCA **次轴**投影跨度 (km) | 仅 K_outer = 1 |
| **R** = outer_ratio | L / W (长宽比) | 仅 K_outer = 1 |
| **D** = convex_hull_diameter_km | 外层那唯一簇 GPS 凸包直径 = 最远两点距离 (km) | 仅 K_outer = 1 |
| **T** = trace_length_km | 按 timestamp 排序后, 相邻点折线累加总长 (km) | 仅 K_outer = 1 |
| **τ** = tortuosity | T / D (曲折度) | 仅 K_outer = 1 |
| **gap** = inter_outer_gap_km | K_outer 簇凸包间最小距离 (km) | 仅 K_outer ≥ 2 |
| **transit** = max_transit_kmh | 时序相邻照片对 (Δt ≥ 20 min) 的距离 / 时间最大值 (kmh); 若全部相邻对 Δt < 20 min → null | 任何时候 |

⚠ **L/W/R 永远来自 outer 那唯一一簇**, K_inner 只是"内部结构指示器", **仅用于 A1.5 linear 判定**。

⚠ **T 用 timestamp 仅做"排序", 不参与判定语义** — T 本身是空间属性 (折线长度), 跟 time 维度的双峰检测 / 跨度判定**不冲突**。

---

## 二、算法步骤

### 2.1 · 整体流水线

```text
照片列表 (含 GPS + timestamp)
       │
       ▼
┌──────────────────────────────────────────┐
│ Phase 1 · 几何预处理                       │
│  · 经纬度 → 局部米制坐标 (centroid 为原点)  │
│  · 外层 DBSCAN(eps=1500m, min_samples=2)  │
└──────────────────────────────────────────┘
       │
   分支根据 K_outer:
   ┌──────────┼──────────┬───────────┐
   ▼          ▼          ▼           ▼
 K_outer=0  K_outer=1  K_outer=2  K_outer≥3
   │          │           │          │
   │          ▼           ▼          │
   │   ┌─────────────┐  ┌────────┐   │
   │   │ Phase 2     │  │ 路径 B │   │
   │   │ 内层 DBSCAN │  │ 单步   │   │
   │   │ + PCA OBB   │  │ 判定   │   │
   │   │ + 凸包直径   │  └────────┘   │
   │   │ + 轨迹长度   │       │       │
   │   │ + transit   │       ▼       │
   │   └─────────────┘  band ∈ 4 档  │
   │          │                       │
   │          ▼                       │
   │   ┌─────────────┐                │
   │   │ Phase 3     │                │
   │   │ Step A1     │                │
   │   │ PCA 基础 band│                │
   │   └─────────────┘                │
   │          │                       │
   │          ▼                       │
   │   ┌─────────────┐                │
   │   │ Step A2     │                │
   │   │ 形状校正 (τ)│                │
   │   └─────────────┘                │
   │          │                       │
   │          ▼                       │
   │   ┌─────────────┐                │
   │   │ Step A3     │                │
   │   │ transit 降档 │                │
   │   └─────────────┘                │
   │          │                       │
   ▼          ▼                       ▼
  none    band ∈ 4 档                none
       (终值)
```

### 2.2 · Phase 1 · 几何预处理

#### 2.2.1 · 经纬度 → 局部米制坐标

以照片 GPS 的几何中心 (centroid) 为原点:

```python
def to_local_meters(gps_list: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """GPS (lat, lng) → 局部平面 (x_m, y_m)."""
    lat0 = mean(lat for lat, _ in gps_list)
    lng0 = mean(lng for _, lng in gps_list)
    # 1° 纬度 ≈ 111 km; 1° 经度 ≈ 111 × cos(lat) km
    return [
        (
            (lng - lng0) * 111_000 * cos(radians(lat0)),
            (lat - lat0) * 111_000,
        )
        for lat, lng in gps_list
    ]
```

⚠ 对 v0.1 单次上传 (跨度 ≤ 数十 km) 来说线性近似精度足够。 大跨度 (跨国) 需更精确的等距投影 (留 OQ-017 弹性时机评估)。

#### 2.2.2 · DBSCAN (手撸, 不引 sklearn)

```python
def dbscan(points_xy: list[tuple[float, float]], eps_m: float, min_samples: int) -> list[int]:
    """返回每个点的 cluster_id (0/1/2/..) 或 -1 (outlier)."""
    n = len(points_xy)
    labels = [-1] * n
    visited = [False] * n
    cluster_id = 0
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = [j for j in range(n) if euclidean(points_xy[i], points_xy[j]) <= eps_m]
        if len(neighbors) < min_samples:
            continue  # outlier
        labels[i] = cluster_id
        queue = list(neighbors)
        while queue:
            j = queue.pop()
            if not visited[j]:
                visited[j] = True
                j_neighbors = [k for k in range(n) if euclidean(points_xy[j], points_xy[k]) <= eps_m]
                if len(j_neighbors) >= min_samples:
                    queue.extend(j_neighbors)
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1
    return labels
```

时间复杂度 O(n²), 对 v0.1 单次上传 ≤ 50 张照片可忽略。

**外层** `dbscan(points, eps_m=1500, min_samples=2)` → K_outer + outliers
**内层** `dbscan(cluster_points, eps_m=500, min_samples=2)` → K_inner (仅 K_outer=1 时跑)

### 2.3 · Phase 2 · K_outer = 1 几何特征计算

#### 2.3.1 · PCA OBB (主轴 / 次轴跨度, 纯 Python 实现)

⚠ 项目栈无 numpy 依赖, 2D PCA 用 **2×2 协方差矩阵闭式解** (不需要数值迭代):

```python
def pca_obb(cluster_xy: list[tuple[float, float]]) -> tuple[float, float, float]:
    """返回 (L_km, W_km, R). 输入米制坐标."""
    n = len(cluster_xy)
    cx = sum(x for x, _ in cluster_xy) / n
    cy = sum(y for _, y in cluster_xy) / n
    # 协方差矩阵 [[a, b], [b, d]]
    a = sum((x - cx) ** 2 for x, _ in cluster_xy) / n
    d = sum((y - cy) ** 2 for _, y in cluster_xy) / n
    b = sum((x - cx) * (y - cy) for x, y in cluster_xy) / n
    # 2×2 矩阵特征值闭式解
    trace = a + d
    det = a * d - b * b
    disc = max(0.0, (trace / 2) ** 2 - det)
    sqrt_disc = disc ** 0.5
    lam_max = trace / 2 + sqrt_disc          # 主轴方差
    lam_min = trace / 2 - sqrt_disc          # 次轴方差
    # 主轴方向 (单位向量)
    if abs(b) > 1e-9:
        v1 = (lam_max - d, b)
    else:
        v1 = (1.0, 0.0) if a >= d else (0.0, 1.0)
    norm = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
    v1 = (v1[0] / norm, v1[1] / norm)
    v2 = (-v1[1], v1[0])                     # 次轴 ⊥ 主轴
    # 投影跨度
    proj_v1 = [(x - cx) * v1[0] + (y - cy) * v1[1] for x, y in cluster_xy]
    proj_v2 = [(x - cx) * v2[0] + (y - cy) * v2[1] for x, y in cluster_xy]
    L = (max(proj_v1) - min(proj_v1)) / 1000.0   # m → km
    W = (max(proj_v2) - min(proj_v2)) / 1000.0
    R = L / W if W > 1e-6 else float("inf")
    return L, W, R
```

#### 2.3.2 · 凸包直径

```python
def convex_hull_diameter_km(cluster_xy: list[tuple[float, float]]) -> float:
    """凸包顶点两两最远距离, 单位 km."""
    hull = convex_hull(cluster_xy)           # 输出凸包顶点列表
    max_d = 0.0
    for i in range(len(hull)):
        for j in range(i + 1, len(hull)):
            d = euclidean(hull[i], hull[j])
            if d > max_d:
                max_d = d
    return max_d / 1000.0
```

凸包 `convex_hull` 用 Andrew's monotone chain 算法 (O(n log n))。

#### 2.3.3 · 轨迹长度 + 曲折度

```python
def trace_length_km(photos_sorted_by_ts: list[Photo]) -> float:
    """按 timestamp 升序连相邻点折线, 累加距离."""
    total_m = 0.0
    for i in range(len(photos_sorted_by_ts) - 1):
        total_m += haversine_m(
            photos_sorted_by_ts[i].gps,
            photos_sorted_by_ts[i + 1].gps,
        )
    return total_m / 1000.0


tortuosity = trace_length_km / convex_hull_diameter_km
```

⚠ 边界: K_outer=1 但 cluster 内只有 2 点 (n=2) 时 D = 两点距离, T = 两点距离, τ = 1 (退化为线性)。

#### 2.3.4 · transit (20 min 间隔过滤)

```python
def max_transit_kmh(photos_sorted_by_ts: list[Photo], min_interval_min: int) -> float | None:
    """时序相邻对, 间隔 ≥ min_interval_min 才计入. 取最大值."""
    speeds = []
    for i in range(len(photos_sorted_by_ts) - 1):
        delta_min = (photos_sorted_by_ts[i + 1].ts - photos_sorted_by_ts[i].ts).total_seconds() / 60
        if delta_min < min_interval_min:
            continue
        d_km = haversine_km(photos_sorted_by_ts[i].gps, photos_sorted_by_ts[i + 1].gps)
        speed_kmh = d_km / (delta_min / 60)
        speeds.append(speed_kmh)
    return max(speeds) if speeds else None
```

⚠ 20 min 阈值的设计意图: 防 GPS 漂移瞬时速度膨胀 (例: 两张连拍间隔 30 秒, 漂移 200m → 老算法算 24 kmh 误判跨点)。

---

## 三、Step A1 · PCA 基础 band (9 行网格)

按行顺序匹配, 第一条命中即为基础 band:

| # | L (km) | W (km) | R | K_inner | 基础 band | shape |
|---|---|---|---|---|---|---|
| A1.1 | > 5 | — | — | — | **none** | oversized |
| A1.2 | — | > 1.5 且 L > W | — | — | **none** | oversized |
| A1.3 | — | ≥ 1.5 | > 5 | — | **none** | oversized |
| A1.4 | ≤ 0.5 | — | — | — | **strong** | compact |
| A1.5 | ≤ 5 | < 0.5 | > 5 | = 1 | **strong** | linear |
| A1.6 | ≤ 1.5 | — | ≤ 5 | — | **strong** | compact |
| A1.7 | ≤ 3 | ≤ 1.5 | — | — | **medium** | stretched |
| A1.8 | > 3 且 ≤ 5 | ≤ 1.5 | — | — | **medium** | extended |
| A1.9 | 其他 | — | — | — | **weak** | irregular |

### 3.1 · A1.5 linear 的 K_inner = 1 限制

只有内层也只有一簇 (eps=500m 还连得起) 时, PCA 的"窄长条" 才可信为真步行街/湖边/沿江步道。 K_inner ≥ 2 表示长条是**退化形状**:

```text
退化示例: A 拍 2 张 + B 拍 2 张, 各组 GPS 几乎重合, 间距 1km

x x  · · · · · · · · · · · ·  x x
A 点 ←──────── 1 km ────────→ B 点

外层 DBSCAN(eps=1500m): 全部连成 K_outer=1
内层 DBSCAN(eps=500m):  A 簇 + B 簇 → K_inner=2

PCA 主轴 = AB 连线
L = 1km (合理)
W ≈ 0 (各组 GPS 重合, 离主轴几乎 0 距离)
R = ∞

若无 K_inner 限制, 命中 A1.5 → strong (linear) ❌
有 K_inner=1 限制, 顺延到 A1.7 → medium ✓
```

### 3.2 · 网格行解读

- **A1.1 / A1.2 / A1.3**: 三道 "oversized 拦截" 大门, L 过长或 W 过宽 / R 极端长宽比 → 直接判散
- **A1.4**: 紧凑团状 (跨度 ≤ 500m), 任何形状都 strong (咖啡店 / 小商场 / 紧凑景点)
- **A1.5**: 真线性 (沿街/沿河/沿江, K_inner=1 保证连续), R > 5 + W < 500m → strong
- **A1.6**: 一片合理紧凑区域 (≤ 1.5km × 不太狭长), strong
- **A1.7**: 大景区慢游, 长 ≤ 3km, 宽 ≤ 1.5km, medium
- **A1.8**: 更大跨度但仍合理 (3 < L ≤ 5km, W ≤ 1.5km), medium
- **A1.9**: 其他 (兜底), 通常是 1.5km < L ≤ 3km + R > 5 + W ≥ 0.5km 这种"半窄长条但不够 linear" 的奇怪形状 → weak

---

## 四、Step A2 · 形状校正 (τ 信号补丁)

PCA 假设点云有"主延伸方向"(矩形/椭圆/线性), 但**环形 / U 形 / 圈形**失效。 用 τ 信号补救。

| # | A1 输出 | τ 条件 | 几何兜底 | 校正后 band | 新 shape |
|---|---|---|---|---|---|
| A2.1 | **none** (从 A1.1 或 A1.2 来) | τ > 2 | L ≤ 8 且 W ≤ 3 | **medium** | loop / u_shape |
| A2.2 | **strong** (从 A1.5 linear 来) | τ > 1.5 | — | **medium** | linear_curved |
| A2.3 | 其他 (含 A1.3 oversized, A1.4/A1.6/A1.7/A1.8/A1.9) | — | — | 不变 | 沿用 A1 |

### 4.1 · A2.1 解读: 环湖 / U 形大景区救援

A1 把环湖游 (3 × 2km 椭圆湖) 误杀成 none (因 W > 1.5 触发 A1.2), 但 τ > 2 说明实际是绕路 + 跨度合理 (L ≤ 8km, W ≤ 3km) → 平反到 medium。

直觉: τ = 走路总长 / 直线跨度。 圆周率 π ≈ 3.14, 绕完一个圆 τ ≈ π; U 形步道 τ 在 2~3 之间; 真路过 τ ≈ 1。

### 4.2 · A2.2 解读: 弯曲步道降档

A1.5 认为窄长条 = 真步行街 = strong, 但 τ > 1.5 说明它弯曲 (不是直线), 不是真步行街 → 降到 medium。

例: 一条 S 形步道, GPS 沿 S 走, PCA 算出 L 大 / W 小 / R 大 → A1.5 命中 strong, 但实际 τ ≈ 1.5+ → 应当 medium。

### 4.3 · 不做的事

⚠ **不做 τ > 4 穿梭降档** (ADR-0010 §2.5 明示)。 原因: τ 大不一定是反例, 可能是用户在同一店来回拍照, T 膨胀但实际同点, 误杀概率高。

---

## 五、Step A3 · transit 降档

```python
if max_transit_kmh is not None and max_transit_kmh >= 30.0:
    if band == "strong":  band = "medium"
    elif band == "medium":  band = "weak"
    # weak / none 不动
```

### 5.1 · 直觉

transit ≥ 30 kmh + 20 min 间隔 ≥ 10 km 跨度, 这是开车跨点的速率。 命中即"chain 合并是开车假象, 不是步行慢游" → 降一档。

### 5.2 · transit = null 的处理

所有相邻对 Δt < 20 min → null。 此时不降档 (信号缺失, 不主动归责)。

诊断字段 `transit_unknown` 落痕给 LLM, 让上层有机会做二次复审 (本 ADR 不做)。

---

## 六、路径 B · K_outer = 2 (双簇单步判定)

| # | gap (km) | transit (kmh) | band | shape |
|---|---|---|---|---|
| B.1 | ≤ 0.5 | — | **strong** | multi_close |
| B.2 | ≤ 2 | < 20 或 null | **medium** | multi_walk |
| B.3 | ≤ 2 | ≥ 20 | **weak** | multi_drive |
| B.4 | > 2 | — | **none** | multi_far |

### 6.1 · 直觉

- **B.1 (gap ≤ 500m)**: 两簇靠很近, 通常是步行街中段 GPS 缺失 / 两个紧邻的小景点 → strong
- **B.2 (gap ≤ 2km + 步行)**: 同城慢游多点, medium
- **B.3 (gap ≤ 2km + 开车)**: 跨点假合并, weak
- **B.4 (gap > 2km)**: 跨城 / 跨大景区, none

### 6.2 · 为什么双簇不引入 D/T/τ

双簇场景 τ 含义不直观 (T 跨 gap 反复, 失去"曲折度"语义)。 gap + transit 已足够区分"步行多点游" vs "开车跨城"。

---

## 七、场景验证

### 7.1 · 设计目标场景 (Ace 2026-05-15 提出)

| 场景 | L | W | R | D | T | τ | K_inner | gap | transit | 命中 | band |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 西湖一日游 (5 张, 3.2km, 5h 步行) | 3.2 | 0.6 | 5.3 | 3.2 | 5.0 | 1.56 | 3 | — | 2 | A1.8 → A2 不命中 → A3 不降 | **medium** |
| 南京路步行街 (4 张沿街 1.2km) | 1.2 | 0.05 | 24 | 1.2 | 1.2 | 1.0 | 1 | — | 3 | A1.5 → A2 不命中 → A3 不降 | **strong** |
| 千岛湖湖边 (6 张沿湖 2.5km) | 2.5 | 0.04 | 62 | 2.5 | 2.6 | 1.04 | 1 | — | 4 | A1.5 → A2 不命中 → A3 不降 | **strong** |
| 跨城开车 (2+2, 杭州+临安 25km) | — | — | — | — | — | — | N/A | 25 | 30 | B.4 | **none** |
| 退化双簇 (A 2 + B 2, 间距 1km) | 1.0 | 0.01 | 100 | 1.0 | 1.0 | 1.0 | 2 | — | 2 | A1.5 不命中 (K_inner=2) → A1.7 | **medium** |
| 环湖游 (3×2km 椭圆湖, 绕一圈 8km) | 3.0 | 2.0 | 1.5 | 3.2 | 8.0 | **2.5** | 4+ | — | 3 | A1.2 → **A2.1 命中** | **medium** |
| 同城跨点 chain (上午 A + 路 + 下午 B, 步行) | 1.0 | 0.01 | 100 | 1.0 | 1.0 | 1.0 | 2 | — | 2 | A1.7 (K_inner=2 不进 A1.5) | **medium** |
| 同城跨点 chain (上午 A + 路 + 下午 B, 开车) | 4.0 | 0.5 | 8 | 4.0 | 4.0 | 1.0 | 2 | — | 35 | A1.8 → A3 命中 | **weak** |

### 7.2 · 暂不修复的边界场景 (Ace 2026-05-15 接受)

| 场景 | L | τ | 命中 | band | 备注 |
|---|---|---|---|---|---|
| 沿江步道 5.5km (直线散步 1.5h) | 5.5 | 1.0 | A1.1 → A2.1 不命中 (τ=1) | **none** | L > 5 硬边界, OQ-017 触发后用 cross_province 弹性 eps |
| U 形栈道 (1km × 0.5km, 走 4km) | 1.0 | 4.0 | A1.6 → A2.2 不命中 (不是 A1.5) | **strong** | 1km 跨度仍合理, τ > 4 不降档 (Ace 接受) |

---

## 八、核心不变性

1. **band 输出严格 ∈ {strong, medium, weak, none}**, 4 档 strength, 真值表直接消费, 无第 5 档
2. **K_outer 是路径分流主键**: 0 → none, 1 → 三层 (A1→A2→A3), 2 → 单步 B, ≥3 → none
3. **K_inner 仅 K_outer=1 时计算**, 否则 None
4. **L / W / R / D / T / τ 永远来自外层那唯一一簇** (K_outer=1)
5. **transit 必须 Δt ≥ 20 min 才计入** — 防 GPS 漂移瞬时膨胀
6. **τ 用 timestamp 仅做排序**, 不参与判定语义 (T 是空间属性, 跟 time 维度不冲突)
7. **不外挂 HR-POST 跨维度兜底** — 跨维度歧义在 location 内部由 A2 形状校正 + A3 transit 降档消化
8. **真值表 28 条结构不变** — band 直出, 不读 `dimension_bands.location` 阈值表
9. **市内 chain 默认接受** (产品语义合理), 落痕 shape=stretched 留 LLM 兜底
10. **rule_fired 必填** — 落痕格式 `"A1.7"` / `"A2.1"` / `"A3_transit_demote"` / `"B.2"` 等, 便于事后归因

---

## 九、配置

完整配置见 [config/path_b_location.yaml](../config/path_b_location.yaml)。

### 9.1 · 关键参数 + 含义

| 参数 | 默认值 | 含义 |
|---|---|---|
| `dbscan.eps_outer_m` | 1500 | 外层 DBSCAN eps, 活动边界粒度 |
| `dbscan.eps_inner_m` | 500 | 内层 DBSCAN eps, 内部结构粒度 |
| `dbscan.min_samples` | 2 | DBSCAN 最小样本数 |
| `a1_grid.l_oversized_km` | 5.0 | A1.1 L 上限 |
| `a1_grid.w_oversized_km` | 1.5 | A1.2/A1.3 W 边界 |
| `a1_grid.r_oversized` | 5.0 | A1.3/A1.5 R 边界 |
| `a1_grid.l_linear_max_km` | 5.0 | A1.5 linear L 上限 |
| `a1_grid.w_linear_max_km` | 0.5 | A1.5 linear W 上限 |
| `a2_correction.tortuosity_loop_threshold` | 2.0 | A2.1 τ 边界 |
| `a2_correction.l_loop_max_km` | 8.0 | A2.1 L 兜底 |
| `a2_correction.tortuosity_curved_threshold` | 1.5 | A2.2 τ 边界 |
| `a3_transit.transit_demote_kmh` | 30.0 | A3 降档阈值 |
| `a3_transit.min_interval_minutes` | 20 | transit 最小间隔过滤 |
| `path_b_dual.gap_close_km` | 0.5 | B.1 |
| `path_b_dual.gap_walk_max_km` | 2.0 | B.2/B.3 共用 |
| `path_b_dual.transit_walk_kmh` | 20.0 | B.2/B.3 分界 |

---

## 十、OQ 关联

| OQ | 状态 |
|---|---|
| [OQ-009 §9a](./12_open_questions.md#oq-009-多维度匹配分档-multi-cross-算法严格度) (路径 B location 严格度) | **本 ADR (0010) 关闭** — 直出 band 替代 score → 阈值, 严格度问题消解 |
| [OQ-017](./12_open_questions.md#oq-017-poi-城市判定接入后-location-档位回切计划) (POI 接入后档位弹性) | 不变 — 本 ADR 只动路径 B, 路径 A unified 档位仍待 OQ-017 触发 |
| OQ-021 (新增候选) | 真实数据上市内 chain 接受度验证 (本 doc §2.8 / ADR-0010 §2.8 接受假设需 v0.2 验证) |

---

## 十一、关联

**ADR**:
- [ADR-0010](../decisions/0010-path-b-location-dbch-pca-shape.md) (本规范的决策依据)
- [ADR-0004](../decisions/0004-feature-assembler-revision.md) §3.2.1 (location_score, 被 ADR-0010 supersede)
- [ADR-0005](../decisions/0005-place-anchor-dbch.md) (路径 A DBCH, 同源算法但目标不同)
- [ADR-0007](../decisions/0007-unified-location-bands.md) (路径 A unified 距离档位, 不影响路径 B)

**Docs**:
- [docs/02 §LocationFeature](./02_data_contracts.md) (字段定义)
- [docs/07 §3.2.1](./07_dimension_thresholds.md) (location 章节, 引用本 doc)
- [docs/10 §二 Place Anchor](./10_mini_album_schema.md) (路径 A DBCH 对照)

**代码**:
- `src/features/location.py::build_location_feature` (本 doc 算法实现)
- `src/contracts/features.py::LocationFeature` (落痕结构)
- `config/path_b_location.yaml` (配置全集)
