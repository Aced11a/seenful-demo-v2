# ADR-0016 · Location 维度 · Geocoder 接入 + 4 档升级

| 字段 | 值 |
|---|---|
| 状态 | accepted |
| 决策日期 | 2026-05-18 |
| 决策人 | Ace — 拍板 POI/4 档/国内/直接接入/v0.1 demo |
| 影响范围 | 新增 `src/mini_album/geocoder.py` (AmapGeocoder + MockGeocoder) + 升 `src/contracts/place_anchor.py::HomeCityRegion + Context` + 改 `src/mini_album/user_home_city.py + place_anchor.py` + 新增 `config/geocoder.yaml` + 改 `config/place_anchor.yaml` (3 档→4 档) + 新增 `docs/22_location_geocoder.md`; 改 `docs/{00,01,02,07,10,11,12}` |
| 相关文档 | `docs/22_location_geocoder.md`; `Location_Geocoder_4Tier_Spec.md` v0.1 (设计来源, 实施完后归档) |
| 关联 OQ | **关闭** OQ-005 (home_city 缺失默认) / OQ-010 §10a (聚类粒度) / **部分关闭** §10b (兜底) / OQ-017 (POI 后档位回切); 新增 [OQ-027](../docs/12_open_questions.md#oq-027-adr-0016-接受边界的真实数据验证) (5 子问题) |
| 关联 ADR | **supersede** [ADR-0007](./0007-unified-location-bands.md) (临时单一档位); **扩展** [ADR-0005](./0005-place-anchor-dbch.md) 距离档位 3 档 → 4 档; **不影响** [ADR-0010](./0010-path-b-location-dbch-pca-shape.md) (path B location 已删 LocationContext) |

---

## 1 · 背景

### 1.1 · 现状失败模式 (实测验证)

| 场景 | 老 `same_province_china_simplified` | 真实归属 |
|---|---|---|
| 杭州 ↔ 上海 (168km) | 同省 ❌ | 跨省 |
| 杭州 ↔ 苏州 (180km) | 同省 ❌ | 跨省 |
| 北京 ↔ 天津 (113km) | 同省 ❌ | 跨省 |
| 萧山机场 ↔ 杭州市中心 (40km) | (跟距离判同省 OK 但跟 30km 半径漏判) | 同市 |

ADR-0007 临时单一档位 (500/1000/2000m) 同样不解, 当前是"等回切".

### 1.2 · 引发本 ADR 的具体问题

- ADR-0007 OQ-017 回切前置依赖
- OQ-005 + OQ-010 §10a 需要真实行政区判定
- 红线 §7 ("高频地点不能仅凭 GPS 自动并入") 依赖准确判定

### 1.3 · Ace 拍板路线 (2026-05-18)

1. POI 路线 (高德 Reverse Geocoding API, 非 PIP 离线 polygon)
2. 高德 30 万次/天免费 quota, 零成本
3. 针对国内 (海外 v0.3)
4. v0.1 demo 直接接入 (provider 双轨)
5. 4 档升级 (市内/省内/国内/国外)
6. 距离阈值: strong = 500/1000/1500/2000m, medium/weak 按 1:2:4 比例派生

---

## 2 · 决策

### 2.1 · 算法范式

**Geocoder 接口抽象** + **provider 双轨** (mock for CI, amap for runtime):
- `MockGeocoder`: 固定 dict 映射 (CI 测试 / 无 API key 时用)
- `AmapGeocoder`: 调高德 Reverse Geocoding API

返回 admin dict: `{country, province, city, district}`.

### 2.2 · 4 档判定逻辑

```python
def get_context_4tier(photo_admin: dict, user_home: dict) -> Context:
    """市内 / 省内 / 国内 / 国外."""
    if photo_admin is None or photo_admin.get("country") is None:
        return "市内"  # 兜底 (OQ-005 保守)
    if photo_admin["country"] != user_home["country"]:
        return "国外"
    if photo_admin["province"] != user_home["province"]:
        return "国内"
    if photo_admin["city"] != user_home["city"]:
        return "省内"
    return "市内"
```

### 2.3 · DBCH 距离档位 4 档 × 3 档 = 12 阈值

| 档位 | strong (m) | medium (m) | weak (m) |
|---|---|---|---|
| **市内** | **500** | 1000 | 2000 |
| **省内** | **1000** | 2000 | 4000 |
| **国内** | **1500** | 3000 | 6000 |
| **国外** | **2000** | 4000 | 8000 |

⚠ Ace 暂定 strong = 500/1000/1500/2000m (跟 ADR-0007 临时表的 500m strong 衔接). medium/weak 按 1:2:4 比例派生.

### 2.4 · DBSCAN eps 4 档

| 档位 | eps_m |
|---|---|
| 市内 | 200 (跟原 home_city 同) |
| 省内 | 400 (跟原 cross_province 同) |
| 国内 | 600 (新加, 平均) |
| 国外 | 800 (跟原 cross_country 同) |

### 2.5 · Buffer base 4 档

按 `strong / 2` 派生:

| 档位 | base_m |
|---|---|
| 市内 | 250 |
| 省内 | 500 |
| 国内 | 750 |
| 国外 | 1000 |

### 2.6 · 缓存机制

- GPS 量化 4 位小数 (~ 10m) 作 cache key
- 进程内 dict 缓存 (demo 阶段)
- None 也缓存 (避免重复打 quota 在失败 GPS 上)
- 不重试 (网络异常返 None)

### 2.7 · API key 管理

- 环境变量 `AMAP_API_KEY` (不进 git)
- AmapGeocoder.__init__ 检查, 缺失时 raise (但默认 provider="mock", 不强制 key)

### 2.8 · 配置

```yaml
# config/geocoder.yaml
geocoder:
  provider: "mock"                    # 默认 mock 安全 (无 key 也能跑)
  # provider: "amap"                  # 想真接入改这行 + 设 AMAP_API_KEY env var

  amap:
    api_key_env: "AMAP_API_KEY"
    endpoint: "https://restapi.amap.com/v3/geocode/regeo"
    timeout_seconds: 5
```

⚠ **yaml default mock 而非 amap** (跟 spec §6.1 修订): 这样无 key 状态下所有测试 + golden 都能跑; Ace 想真接入手动改 yaml + 设 env var.

---

## 3 · 评估过的备选项

| 方案 | 拒绝理由 |
|---|---|
| A. 老距离判同省 (`same_province_china_simplified`) | 大量误判 (杭州↔上海 168km 判同省) |
| B. ADR-0007 临时单一档位 | 等回切但回切前置 (POI 接入) 未解 |
| C. PIP 离线 polygon (Storyo 思想) | 我推荐过, Ace 选 POI 路线 |
| D. 百度/Google Maps API | 国内 + 免费 → 高德是更好选择 |
| **E. 本 ADR — 高德 + 4 档 + provider 双轨** | 实测可行 + 零成本 + 准确率高 + 4 档语义清晰 |

---

## 4 · 影响范围

### 4.1 · 契约变更

**`HomeCityRegion`** 扩字段:
```python
class HomeCityRegion(BaseModel):
    user_id: str
    country: str = "中国"
    province: str | None = None
    city: str | None = None
    district: str | None = None
    center: tuple[float, float] | None = None    # 兜底用, 不再主判定
    radius_km: float | None = None               # 同上
    inferred_at: datetime | None = None
    inferred_source: str = "stub"                # "stub" / "amap_frequency"
```

**`Context`** 枚举改中文 4 档:
```python
# 老:
Context = Literal["home_city", "cross_province", "cross_country"]

# 新:
Context = Literal["市内", "省内", "国内", "国外"]
```

### 4.2 · 新增算法模块

`src/mini_album/geocoder.py` (~ 200 行):
- `MockGeocoder` (固定 dict, CI 测试用)
- `AmapGeocoder` (调高德 API, demo + 生产)
- `get_geocoder(cfg)` factory
- `gps_to_cache_key(lng, lat)` 量化函数

### 4.3 · 修改算法模块

`src/mini_album/user_home_city.py`:
- 删 `same_province_china_simplified`
- 改 `get_context_for_photo` → `get_context_4tier`
- 改 `infer_user_home_city` 用 admin dict (stub 阶段仍硬编码, OQ-010 §10c v0.2 真接)
- `get_album_context` 4 档严格度排序

`src/mini_album/place_anchor.py`:
- 改 `distance_to_band(d_m, context, cfg)` 真下钻 context (恢复 ADR-0005 设计)
- 读 `cfg["band_thresholds_4tier"]` 4 档表

### 4.4 · 配置变更

`config/place_anchor.yaml`:
- **删** `unified_band_thresholds` (ADR-0007 临时表)
- **删** `unified_buffer`
- **加** `band_thresholds_4tier` 12 阈值
- **加** `buffer_4tier` 4 base
- **改** `dbscan.eps_m` 加"省内"档

新增 `config/geocoder.yaml` (provider 双轨).

### 4.5 · 测试

`tests/unit/test_geocoder.py` 新增 (~ 100 行 + monkeypatch HTTP).
`tests/conftest.py` 加 autouse fixture 强制 provider=mock.
现有 `test_user_home_city.py` / `test_place_anchor.py` 改 4 档 case.
单测 + 重生 golden.

---

## 5 · 回滚条件

| 回滚条件 | 动作 |
|---|---|
| 高德 API 频繁失败 (> 10%) | 回 ADR-0007 单一档位 + 高频地点降一档 (退步但能跑) |
| 4 档准确率 < 90% | 调阈值 (medium/weak 比例) |
| 海外用户量 > 5% | 触发 v0.3 加 Google Maps Geocoding 双轨 |

---

## 6 · OQ 状态变更

| OQ | 之前 | 现在 |
|---|---|---|
| OQ-005 (home_city 缺失默认) | 临时决策 (home_city 保守) | **关闭** — amap country fallback "中国" + photo_admin=None 兜底"市内" |
| OQ-010 §10a (聚类粒度 city/district) | 待 v0.2 | **关闭** — amap 直出 country/province/city/district |
| OQ-010 §10b (数据不足回退) | 待决 | **部分关闭** — amap 异常返回 None, 兜底"市内" |
| OQ-010 §10c (用户搬家检测) | 待决 | **不变** — v0.2 通过 30 天 GPS 频次刷新 home_city |
| OQ-010 §10d (多 home_city) | 待决 | **不变** — P1 |
| **OQ-017** (POI 接入后档位回切) | 待 OQ-010 完成 | **关闭** — 本 ADR 即为回切 |
| ADR-0007 状态 | accepted (临时) | **superseded** by 本 ADR |
| **OQ-027 (新增)** | — | 5 子问题 (量化粒度/海外/重试/缓存/搬家) |

---

## 7 · 后续动作

1. ✅ 本 ADR 写完
2. ⏳ `docs/22_location_geocoder.md` 完整算法规范
3. ⏳ `config/geocoder.yaml` + `config/place_anchor.yaml` 4 档
4. ⏳ `src/mini_album/geocoder.py` 新增
5. ⏳ HomeCityRegion + Context 升级
6. ⏳ `user_home_city.py` + `place_anchor.py` 4 档适配
7. ⏳ 跨 docs 同步 + OQ 状态更新
8. ⏳ 单测 + conftest 强制 mock + 重生 golden + grep 自检 + 归档 spec
9. ⏳ Ace 设置 `AMAP_API_KEY` env var (10 分钟, 想真接入时再做)
