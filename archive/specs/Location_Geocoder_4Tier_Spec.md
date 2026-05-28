# Seenful Location 维度 · Geocoder 接入 + 4 档升级规范

> **版本**: v0.1 (draft, 待 Ace 审核)
> **日期**: 2026-05-18
> **适用**: 路径 A (动态生长 L2.5) DBCH location 维度
> **状态**: spec 草稿, 未实施. 审核通过后走 12 步实施 (写 ADR-0016 + 后续 docs/src/config/tests).
>
> **决策来源 (Ace 2026-05-18)**:
> 1. **POI 路线** — 用高德 Reverse Geocoding API (而非 PIP 离线 polygon)
> 2. **零成本** — 高德开发者 key 30 万次/天免费 quota
> 3. **针对国内** — 海外 GPS 走"国外" 兜底, v0.3 国际化时再加 Google Maps
> 4. **v0.1 demo 直接接入** — provider 双轨 (mock for CI, amap for runtime)
> 5. **4 档升级** — 市内 / 省内 / 国内 / 国外 (替换 ADR-0007 临时单一表)

---

## 一、背景

### 1.1 · 现状

| 模块 | 现实现 | 问题 |
|---|---|---|
| `src/mini_album/user_home_city.py::same_province_china_simplified` | distance < 500km → 同省 | ❌ **大量误判**: 杭州↔上海 168km / 北京↔天津 113km / 杭州↔苏州 180km 全被错判同省 |
| `HomeCityRegion.center + radius_km=30` | 距离判 home_city | ❌ 萧山机场 (40km) / 临安区 (40km) 被错判 cross_province; 上海跨度 80km 漏一半 |
| `get_context_for_photo` 3 档 (home_city / cross_province / cross_country) | 用上述 2 个错误判定 | 整体行政区归属不准 |
| ADR-0005 DBCH 距离档位 (home_city/cross_province/cross_country × strong/medium/weak) | 9 阈值表 | 设计正确, 但被 ADR-0007 临时塌缩为单一表 (500/1000/2000m), OQ-017 等回切 |
| `infer_user_home_city` | stub 硬编码 (杭州 30km) | OQ-010 待 v0.2 真接入 |

### 1.2 · 失败模式 (实测验证)

| GPS pair | 距离 | 老 same_province_china_simplified | 真实归属 |
|---|---|---|---|
| 杭州 ↔ 上海 | 168km | 同省 ❌ | 跨省 (浙江 / 上海) |
| 杭州 ↔ 苏州 | 180km | 同省 ❌ | 跨省 (浙江 / 江苏) |
| 北京 ↔ 天津 | 113km | 同省 ❌ | 跨省 (北京 / 天津) |
| 北京 ↔ 廊坊 | 60km | 同省 ❌ | 跨省 (北京 / 河北) |
| 上海市辖区跨度 | 80km | (跟 home_city 30km 半径无关) | 同市 |

### 1.3 · 引发本 spec 的具体问题

- ADR-0007 临时单一表的 OQ-017 回切前置依赖
- OQ-005 (home_city 缺失默认) 待真实判定
- OQ-010 §10a (聚类粒度) 待 v0.2 真接入
- 红线 §7 ("高频地点不能仅凭 GPS 自动并入") 依赖准确的行政区判定

### 1.4 · v0.1 范式核心

```
v0.1 demo 直接接入高德 reverse geocoding API,
不再走 mock-only 路线 (跟 MockJudge / MockEmbedder 不同步).

理由:
1. 高德 30 万次/天免费 quota, demo 量级远不撞顶
2. 真接入立刻见效果, 不用维护 mock 数据跟 fixtures 同步
3. 仍保留 provider 双轨 (CI 测试走 mock 不打 API)
```

---

## 二、核心算法范式

### 2.1 · 设计哲学

| 维度 | 老 (ADR-0007 临时) | **v0.1 (本 spec)** |
|---|---|---|
| 行政区判定 | distance 简化 | **高德 Reverse Geocoding API** |
| 档位数 | 3 档 (home_city / cross_province / cross_country) + 单一阈值表 | **4 档 (市内/省内/国内/国外) + 4 档距离阈值** |
| 数据精度 | 距离启发式 | API 行政区精确 |
| 与 Mock | 全部 mock | **provider 双轨 (mock for CI, amap for runtime)** |
| API key 管理 | 无 | **环境变量** (不进 git) |

### 2.2 · 三阶段流水线

```
photo.exif_location (lng, lat)
   │
   ▼
┌────────────────────────────────────────────┐
│ Phase 1 · 缓存查询 (GPS 量化 4 位小数 ~10m) │
│   命中 → 返回 admin dict                    │
│   未命中 → Phase 2                          │
└────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────┐
│ Phase 2 · Geocoder 调用                     │
│   provider=mock → MockGeocoder (固定 dict)  │
│   provider=amap → AmapGeocoder (调高德 API) │
│   超时 / 异常 → 返回 None                   │
└────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────┐
│ Phase 3 · 4 档判定                          │
│   对比 photo_admin vs user_home_admin        │
│   → 市内 / 省内 / 国内 / 国外               │
└────────────────────────────────────────────┘
```

### 2.3 · 4 档触发条件

| 档位 | 触发条件 |
|---|---|
| **市内** | `photo.country == user.country AND photo.province == user.province AND photo.city == user.city` |
| **省内** | `photo.country == user.country AND photo.province == user.province AND photo.city != user.city` |
| **国内** | `photo.country == user.country AND photo.province != user.province` |
| **国外** | `photo.country != user.country` OR `photo.country is None` (高德返回失败时兜底视为国外) |

⚠ 边界 case:
- photo_admin = None (API 超时/异常) → 兜底 "市内" (保守, 跟老 OQ-005 推荐一致)
- photo GPS 为空 (无 GPS) → 兜底 "市内"

### 2.4 · DBCH 距离档位 (4 档 × 3 档 = 12 阈值)

| 档位 | strong (m) | medium (m) | weak (m) | 设计意图 |
|---|---|---|---|---|
| **市内** | 100 | 300 | 800 | 家附近常去地, 最严. 同小区/同街区算同点 |
| **省内** | 500 | 1500 | 5000 | 杭州人去宁波. 同景区/同商圈算同点 |
| **国内** | 1000 | 3000 | 10000 | 出省旅游. 跨城同景区允许更大跨度 |
| **国外** | 2000 | 5000 | 15000 | 出国旅游. 大景区/异国街区跨度大 |

⚠ 起点阈值来自 ADR-0004 §3.2.1 老 3 档设计 + 推算新加"省内" 档. v0.2 真实数据 grid search 调.

---

## 三、变量定义 + 数据结构

### 3.1 · Admin Dict (Geocoder 返回)

```python
admin = {
    "country": str | None,    # "中国" / "日本" / "美国" / None
    "province": str | None,   # "浙江省" / "上海市" / "北京市" / None
    "city": str | None,       # "杭州市" / "上海市" / "苏州市" / None
    "district": str | None,   # "西湖区" / "黄浦区" / None (可选, 非判定用)
}
```

⚠ 上海/北京/天津/重庆 4 个直辖市: province 字段直接是市名 ("上海市"). 这跟高德 API 返回一致.

### 3.2 · HomeCityRegion 升级

```python
class HomeCityRegion(BaseModel):
    """用户家所在行政区 (v0.1 升级到 4 档)."""
    user_id: str

    # ─── 新加 admin 字段 (v0.1 4 档判定主信号) ────────
    country: str = "中国"
    province: str | None = None          # "浙江省"
    city: str | None = None              # "杭州市"
    district: str | None = None          # "西湖区" (可选)

    # ─── 保留 GPS 中心 (用于 stub / fallback) ────────
    center: tuple[float, float] | None = None    # (lat, lng)
    radius_km: float | None = None       # 兜底用, 4 档判定主要不依赖

    # ─── 数据源诊断 ──────────────────────────────────
    inferred_at: datetime | None = None  # 推断时间
    inferred_source: str = "stub"        # "stub" / "amap_frequency"
```

⚠ `center` + `radius_km` 字段保留但**不再是主判定信号**, 仅作 Geocoder 失败时的 fallback (近似圆形判定).

### 3.3 · Context 枚举升级

```python
# 老 (3 档):
Context = Literal["home_city", "cross_province", "cross_country"]

# 新 (4 档, v0.1):
Context = Literal["市内", "省内", "国内", "国外"]
```

⚠ 中文枚举值 (跟产品语义对齐, 跟用户可见的"小集"中文风格一致).

---

## 四、Geocoder 接口设计

### 4.1 · 抽象接口

```python
class Geocoder(Protocol):
    """Geocoder 协议 (鸭子类型)."""
    def get_admin(self, lng: float, lat: float) -> dict | None:
        ...
```

### 4.2 · MockGeocoder (CI 测试用)

```python
class MockGeocoder:
    """v0.1 demo CI 测试用. 固定 dict 映射, 不打真 API."""

    _FIXTURE = {
        # 量化 GPS (4 位小数 ~ 10m) → admin dict
        # 跟测试 fixtures 配套
        "120.1300,30.2600": {"country": "中国", "province": "浙江省",
                              "city": "杭州市", "district": "西湖区"},
        "120.4300,30.2300": {"country": "中国", "province": "浙江省",
                              "city": "杭州市", "district": "萧山区"},
        "121.4900,31.2400": {"country": "中国", "province": "上海市",
                              "city": "上海市", "district": "黄浦区"},
        # ... 跟 fixtures GPS 一一映射
    }

    def get_admin(self, lng, lat):
        key = f"{lng:.4f},{lat:.4f}"
        return self._FIXTURE.get(key)
```

### 4.3 · AmapGeocoder (v0.1 runtime + 生产)

```python
class AmapGeocoder:
    """高德 Reverse Geocoding API (v0.1 demo 直接接入).

    端点: https://restapi.amap.com/v3/geocode/regeo
    免费 quota: 30 万次/天 (个人开发者 key)
    QPS: 30 (demo 阶段不撞)
    """

    def __init__(self, cfg: dict):
        self.api_key = os.environ.get(cfg["api_key_env"])
        if not self.api_key:
            raise RuntimeError(
                f"AmapGeocoder: 缺环境变量 {cfg['api_key_env']}. "
                "申请: lbs.amap.com/dev/key/app"
            )
        self.endpoint = cfg["endpoint"]
        self.timeout = float(cfg["timeout_seconds"])

    def get_admin(self, lng, lat):
        # 调高德 API + 解析
        # 异常时返回 None
```

### 4.4 · 缓存机制 (demo 简单版)

```python
# 进程内字典缓存, 跨调用持久
_CACHE: dict[str, dict | None] = {}

def get_admin_cached(geocoder, lng, lat):
    key = f"{lng:.4f},{lat:.4f}"     # 量化 ~ 10m
    if key not in _CACHE:
        _CACHE[key] = geocoder.get_admin(lng, lat)
    return _CACHE[key]
```

⚠ v0.1 demo 阶段进程内字典够用. v0.2 生产换 Redis (跨服务共享 + TTL).

---

## 五、Case 验证

### Case A · 杭州西湖 (市内)
```
photo: (120.13, 30.26)
amap: country="中国", province="浙江省", city="杭州市"
user_home: country="中国", province="浙江省", city="杭州市"
对比: 都同 → 市内 ✓
DBCH: strong=100m / medium=300m / weak=800m
```

### Case B · 萧山机场 (市内, 修老 30km 半径漏判)
```
photo: (120.43, 30.23)   # 离市中心 40km
amap: country="中国", province="浙江省", city="杭州市"
对比: city 相同 → 市内 ✓
(老 30km radius 漏判 cross_province; 新 4 档准确判市内)
```

### Case C · 杭州人去宁波 (省内)
```
photo: (121.55, 29.87)   # 宁波东海岸
amap: country="中国", province="浙江省", city="宁波市"
对比: province 同, city 不同 → 省内 ✓
DBCH: strong=500m / medium=1500m / weak=5000m
```

### Case D · 杭州人去上海 (国内, 修老距离判同省错)
```
photo: (121.49, 31.24)   # 上海外滩
amap: country="中国", province="上海市", city="上海市"
对比: province 不同 (浙江省 vs 上海市) → 国内 ✓
DBCH: strong=1000m / medium=3000m / weak=10000m
(老距离 168km < 500km 误判同省; 新 4 档准确判国内)
```

### Case E · 杭州人去日本 (国外)
```
photo: (139.69, 35.69)   # 东京
amap: country="日本" 或 status="0" 失败
对比: country 不同 (中国 vs 日本) 或 None → 国外 ✓
DBCH: strong=2000m / medium=5000m / weak=15000m
```

### Case F · GPS 为空 (兜底)
```
photo.exif_location = None
跳过 Geocoder
返回 admin = None → 兜底"市内" (保守)
```

### Case G · API 超时 (兜底)
```
photo: (120.13, 30.26) 但 API 超时
amap 异常 → 返回 None
缓存 None (避免重复打)
4 档判定: photo_admin=None → 兜底"市内"
```

---

## 六、配置

### 6.1 · `config/geocoder.yaml` (新增)

```yaml
geocoder:
  provider: "amap"                  # mock / amap

  amap:
    api_key_env: "AMAP_API_KEY"     # 环境变量名 (key 不进 git)
    endpoint: "https://restapi.amap.com/v3/geocode/regeo"
    timeout_seconds: 5
    cache_ttl_seconds: null         # null = 永不过期 (内存)

  mock:
    # MockGeocoder 内部硬编码 dict, 此段保留供未来扩展
```

### 6.2 · `config/place_anchor.yaml` 4 档距离阈值

```yaml
# 替换 ADR-0007 临时单一表 (500/1000/2000m)
# 4 档对应 ADR-0005 三档原方案的扩展版

distance_to_band_4tier:
  市内:
    strong_m: 100
    medium_m: 300
    weak_m: 800
  省内:
    strong_m: 500
    medium_m: 1500
    weak_m: 5000
  国内:
    strong_m: 1000
    medium_m: 3000
    weak_m: 10000
  国外:
    strong_m: 2000
    medium_m: 5000
    weak_m: 15000

# 移除 (ADR-0007 supersede):
# distance_to_band_unified: {strong_m: 500, medium_m: 1000, weak_m: 2000}
```

### 6.3 · CI 测试强制 mock

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def force_mock_geocoder(monkeypatch):
    """CI / pytest 自动强制 mock, 不打真 API."""
    monkeypatch.setenv("GEOCODER_PROVIDER_OVERRIDE", "mock")
```

---

## 七、与已落 ADR 的关系

| ADR | 关系 |
|---|---|
| **ADR-0005** (path A DBCH) | 距离档位从 3 档塌缩 → 4 档扩展; OQ-017 回切完成 |
| **ADR-0007** (临时单一档位) | **完全 supersede** by 本 spec; v0.1 直接接 amap, ADR-0007 标 superseded |
| ADR-0006 (高频地点) | 不动 (30 天滚动窗口 + 双 density 仍生效) |
| ADR-0010 (path B location DBCH+PCA) | **不动** — path B 已删 LocationContext, 不依赖 4 档判定 |
| ADR-0011~0015 (path B time/event/theme/anchor/emotional) | 不动 |
| OQ-005 (home_city 缺失默认) | **关闭** — amap 提供 country 兜底"中国" |
| OQ-010 §10a (聚类粒度) | **关闭** — amap 直接返回 country/province/city/district |
| OQ-010 §10b (数据不足回退) | **部分关闭** — amap 异常返回 None, 兜底"市内" |
| OQ-017 (POI 城市判定后档位回切) | **关闭** — 本 spec 即为回切实施 |

---

## 八、不变性

1. **4 档判定基于行政区 admin 字段比较**, 不再用距离启发式
2. **provider 双轨**: mock for CI, amap for runtime
3. **API key 走环境变量**, 不进 git
4. **GPS 量化 4 位小数 (~ 10m) 作缓存 key**, 进程内字典缓存
5. **海外 GPS 兜底"国外"** — 不接 Google Maps, v0.3 国际化时加
6. **photo_admin / user_home_admin = None 时兜底"市内"** (保守, 跟 OQ-005 推荐一致)
7. **距离档位 4 档 × 3 档 = 12 阈值** (推动 ADR-0005 DBCH 直接消费)
8. **GPS 为空 (photo.exif_location is None) 兜底"市内"** (跟 OQ-005 一致)
9. **ADR-0007 临时单一表 supersede**, 完全废弃

---

## 九、待决 OQ (本 spec)

### OQ-27a · GPS 量化粒度 (4 位小数 ~ 10m)

- 当前: `f"{lng:.4f},{lat:.4f}"` (~ 10m 精度)
- 候选: 3 位 (100m) / 4 位 (10m) / 5 位 (1m)
- 4 位是合理折中: 同点照片 (同建筑物) 命中缓存; 跨街道不命中
- 真数据观察缓存命中率调整

### OQ-27b · 海外 fallback 接 Google Maps 时机

- 当前: 海外 GPS → 兜底"国外" + admin=None
- 候选: v0.3 国际化时接 Google Maps Geocoding API
- 决策条件: Seenful 海外用户 > 5% 时启动

### OQ-27c · API 失败重试策略

- 当前: 异常返回 None, 缓存 None (不重试)
- 候选: 失败后 N 秒后重试 / 立即重试 1 次 / 不重试
- 推荐不重试 (失败 GPS 缓存 None 防止重复打 quota)

### OQ-27d · 缓存持久化 (Redis 切换时机)

- v0.1 demo: 进程内字典 (重启丢失)
- v0.2 生产: Redis 跨服务共享 + TTL
- 切换 trigger: 多服务部署时

### OQ-27e · 用户搬家检测 (OQ-010 §10c)

- 当前: HomeCityRegion 推断后缓存
- 真实问题: 用户搬家后 home_city 应该更新
- v0.2 实现: 30 天 GPS 频次聚类 + 滚动窗口自动检测

---

## 十、与老 docs/07 边界对照

| 场景 | 老 (ADR-0007 单一表) | **v0.1 (本 spec 4 档)** |
|---|---|---|
| 杭州西湖 + 萧山机场 (40km) | 距离 40km < 500m 兜底 → 杂乱 | 都判市内 (city 同), 距离 strong=100m → none (40km 远超 800m), **正确判杂乱** ✓ |
| 杭州 + 上海 (168km) | 距离 168km, 单一表 weak=2km → none | 4 档判国内, distance vs 国内 weak=10km → none, **跨城正确** ✓ |
| 同小区 (50m) | strong=500m → strong ✓ | 市内 strong=100m → strong ✓ |
| 同景区 (300m) | strong=500m → strong ✓ | 市内 medium=300m → medium (更严), 同景区也算同点 ✓ |
| 上海地铁全程 (80km) | weak=2km → none | 市内 weak=800m → none, 实际同市但不同点 ✓ |
| 出国旅游同景区 (1.5km) | weak=2km → weak ✓ | 国外 strong=2000m → strong, 国外景区跨度大 → strong 合理 |

---

## 十一、实施清单 (12 步)

| Step | 动作 |
|---|---|
| 1 | 申请高德开发者 key + 配置 `export AMAP_API_KEY=...` (你做, 10 分钟) |
| 2 | 写 `decisions/0016-location-geocoder-4tier.md` |
| 3 | 写 `docs/22_location_geocoder.md` (算法专项规范) |
| 4 | 改 `docs/02_data_contracts.md` (HomeCityRegion 字段扩 + Context 4 档) |
| 5 | 改 `docs/07_dimension_thresholds.md` §3.2.1 (距离档位 3→4) |
| 6 | 改 `docs/00/01/10/11/12` (索引 + 架构 + mini_album + 落痕 + OQ) |
| 7 | 关闭 OQ-005 / OQ-010 §10a/10b / OQ-017; **修订** ADR-0007 → superseded |
| 8 | 写 `config/geocoder.yaml` |
| 9 | 改 `config/place_anchor.yaml` (distance_to_band 3→4) |
| 10 | 写 `src/mini_album/geocoder.py` (MockGeocoder + AmapGeocoder + get_geocoder) |
| 11 | 改 `src/contracts/place_anchor.py::HomeCityRegion + Context` 字段升级 |
| 12 | 改 `src/mini_album/user_home_city.py` (4 档判定 + 删 same_province_china_simplified); 改 `src/mini_album/place_anchor.py` (distance_to_band 4 档); 单测 + conftest 强制 mock + 重生 golden + grep 自检 + 归档 spec |

**预估量级**: ~ 4-5 天. 1 ADR + 1 新 doc + 2 yaml + 3 src + 跨 docs + ~30 单测.

---

## 十二、待 Ace 最终审核

1. **4 档触发条件** (§2.3) — country/province/city 比较, 你认可吗?
2. **DBCH 4 档距离阈值起点** (§2.4 - 100/500/1000/2000m strong) — 推算合理性?
3. **provider 双轨**: mock for CI, amap for runtime — OK?
4. **API key 环境变量** (不进 git) — OK?
5. **海外兜底"国外"** + admin=None (不接 Google Maps v0.1) — OK?
6. **photo/user_admin = None 兜底"市内"** (跟 OQ-005 保守一致) — OK?
7. **ADR-0007 完全 supersede** (距离单一表废弃) — OK?
8. **Context 枚举从英文 (home_city/...) → 中文 (市内/...)** — 跟产品语义对齐? 或保持英文?
9. **关闭 OQ-005 / OQ-010 §10a/10b / OQ-017** — OK?

---

## 十三、版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v0.1 (draft) | 2026-05-18 | 初版, POI/高德 API + 4 档升级 (Ace 拍 POI/4 档/国内/直接接入) + provider 双轨 + 12 阈值表 (4 档 × 3 档) + 关闭 OQ-005/§10a/§10b/OQ-017 + supersede ADR-0007 |
