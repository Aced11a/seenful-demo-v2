# 22 · Location 维度 · Geocoder 接入 + 4 档升级

> 路径 A (动态生长) DBCH location 维度 + user_home_city 推断的算法规范.
> 算法依据: [ADR-0016](../decisions/0016-location-geocoder-4tier.md).
> 跟路径 B location (ADR-0010) **独立** — path B 已删 LocationContext, 不依赖本规范.
>
> ⚠ Ace 拍板路线: POI/高德 API + 4 档 (市内/省内/国内/国外) + 针对国内 + v0.1 demo 直接接入 + provider 双轨

---

## 一、Geocoder 接口

### 1.1 · 抽象协议

```python
class Geocoder(Protocol):
    def get_admin(self, lng: float, lat: float) -> dict | None:
        """GPS → admin dict.

        返回:
          {"country": str, "province": str|None, "city": str|None, "district": str|None}
          或 None (失败 / 海外 / GPS 异常)
        """
```

### 1.2 · MockGeocoder (CI 测试用)

- 固定 dict 映射, 不打真 API
- 跟测试 fixtures 的 GPS 一一对应
- 量化 4 位小数 (`f"{lng:.4f},{lat:.4f}"`) 作 key

### 1.3 · AmapGeocoder (runtime 真接入)

- 端点: `https://restapi.amap.com/v3/geocode/regeo`
- 参数: `key`, `location`, `extensions=base`
- API key: 从 env var `AMAP_API_KEY` 读 (不进 git)
- 超时: 5 秒
- 异常: 返回 None (不抛错, 不重试)
- 免费 quota: 30 万次/天 (个人开发者 key)
- QPS: 30 (demo 阶段不撞顶)

### 1.4 · 缓存

- 进程内 dict, 跨调用持久
- key = `f"{lng:.4f},{lat:.4f}"` (~ 10m 精度量化)
- 命中失败结果 (None) 也缓存 (防止重复打 quota)
- demo 不需要 TTL / Redis (v0.2 生产再加)

### 1.5 · provider 切换

`config/geocoder.yaml::geocoder.provider`:
- `"mock"` (默认): MockGeocoder, 安全, 无 API key 也跑
- `"amap"`: AmapGeocoder, 需设 `AMAP_API_KEY` env var

---

## 二、4 档判定逻辑

### 2.1 · 触发条件

| 档位 | 触发条件 |
|---|---|
| **市内** | photo.country == user.country **AND** photo.province == user.province **AND** photo.city == user.city |
| **省内** | photo.country == user.country **AND** photo.province == user.province **AND** photo.city != user.city |
| **国内** | photo.country == user.country **AND** photo.province != user.province |
| **国外** | photo.country != user.country **OR** photo.country is None |

### 2.2 · 兜底规则

| 情况 | 处理 |
|---|---|
| `photo.exif_location` is None (无 GPS) | 兜底 "市内" (保守, 跟 OQ-005 一致) |
| Geocoder 返回 None (API 失败) | 兜底 "市内" |
| 跨直辖市 (上海/北京/天津/重庆) | province == city (高德返回一致), 判定逻辑无碍 |

---

## 三、DBCH 距离档位 (4 档 × 3 档 = 12 阈值)

| 档位 | strong (m) | medium (m) | weak (m) | 物理含义 |
|---|---|---|---|---|
| **市内** | **500** | 1000 | 2000 | 同小区/同街区 |
| **省内** | **1000** | 2000 | 4000 | 同景区/同商圈 (跨城) |
| **国内** | **1500** | 3000 | 6000 | 跨城同景区 |
| **国外** | **2000** | 4000 | 8000 | 大景区/异国街区 |

⚠ Ace 暂定 strong = 500/1000/1500/2000m (跟 ADR-0007 临时表的 500m strong 衔接). medium/weak 按 ADR-0007 1:2:4 比例派生. 真实数据后调.

## 四、DBSCAN eps (4 档)

| 档位 | eps_m |
|---|---|
| 市内 | 200 |
| 省内 | 400 |
| 国内 | 600 |
| 国外 | 800 |

## 五、Buffer base (4 档)

按 strong / 2 派生:

| 档位 | base_m |
|---|---|
| 市内 | 250 |
| 省内 | 500 |
| 国内 | 750 |
| 国外 | 1000 |

---

## 六、配置 (完整)

### 6.1 · `config/geocoder.yaml`

```yaml
geocoder:
  provider: "mock"                    # 默认 mock 安全 (无 key 也跑)
  # provider: "amap"                  # 真接入: 改这行 + 设 AMAP_API_KEY env var

  amap:
    api_key_env: "AMAP_API_KEY"
    endpoint: "https://restapi.amap.com/v3/geocode/regeo"
    timeout_seconds: 5
```

### 6.2 · `config/place_anchor.yaml` (4 档替换 ADR-0007 单一表)

```yaml
# 距离档位 (ADR-0016 4 档, supersede ADR-0007 unified)
band_thresholds_4tier:
  市内:
    strong_m: 500
    medium_m: 1000
    weak_m: 2000
  省内:
    strong_m: 1000
    medium_m: 2000
    weak_m: 4000
  国内:
    strong_m: 1500
    medium_m: 3000
    weak_m: 6000
  国外:
    strong_m: 2000
    medium_m: 4000
    weak_m: 8000

# Buffer (ADR-0016 4 档)
buffer_4tier:
  alpha: 0.6
  base_m:
    市内: 250
    省内: 500
    国内: 750
    国外: 1000

# DBSCAN eps (ADR-0016 4 档)
dbscan:
  eps_m:
    市内: 200
    省内: 400
    国内: 600
    国外: 800
  min_samples: 2
```

---

## 七、Case 验证

| Case | GPS | photo_admin (amap) | user_home_admin | 4 档 | DBCH band 例 (1.2km) |
|---|---|---|---|---|---|
| 杭州西湖 | (120.13, 30.26) | 中国/浙江省/杭州市/西湖区 | 中国/浙江省/杭州市 | **市内** | weak (1200 < 2000) |
| 萧山机场 | (120.43, 30.23) | 中国/浙江省/杭州市/萧山区 | 中国/浙江省/杭州市 | **市内** ✓ (修老半径漏判) | medium (跟市中心距离 40km 远超 weak, 实际 weak) |
| 宁波东海岸 | (121.55, 29.87) | 中国/浙江省/宁波市 | 中国/浙江省/杭州市 | **省内** | strong (1200 ≤ 1000? no, medium 1000-2000) |
| 上海外滩 | (121.49, 31.24) | 中国/上海市/上海市 | 中国/浙江省/杭州市 | **国内** ✓ (修老距离判同省错) | medium |
| 北京天安门 | (116.40, 39.92) | 中国/北京市/北京市 | 中国/浙江省/杭州市 | **国内** | medium |
| 东京 | (139.69, 35.69) | None (高德海外失败) | 中国/浙江省/杭州市 | **国外** | medium |
| 无 GPS | None | (跳过) | (跳过) | 兜底 **市内** | (DBCH 不算) |

---

## 八、不变性

1. **4 档判定基于行政区 admin 字段比较**, 不再用距离启发式
2. **provider 双轨** (mock for CI / amap for runtime)
3. **yaml default provider="mock"** — 安全, 无 API key 也跑
4. **API key 走环境变量** `AMAP_API_KEY`, 不进 git
5. **GPS 量化 4 位小数 (~ 10m)** 作缓存 key
6. **failure (None) 也缓存**, 不重试
7. **海外 GPS / GPS 异常 → admin=None → 兜底"国外"** (跟 country != user.country 触发条件兼容)
8. **photo_admin=None AND user_home_admin OK → 兜底"市内"** (保守)
9. **Context 中文枚举** ("市内/省内/国内/国外", 跟产品语义对齐)
10. **distance_to_band 4 档下钻 context**, 恢复 ADR-0005 设计 (废 ADR-0007 单一表)

---

## 九、与 ADR-0005/0007/0010 关系

| ADR | 关系 |
|---|---|
| **ADR-0005** (path A DBCH) | 距离档位 3 档 → 4 档扩展; distance_to_band 函数恢复下钻 context |
| **ADR-0007** (临时单一表) | **完全 supersede**, 标 superseded |
| **ADR-0010** (path B location DBCH+PCA) | **不影响** — path B 已删 LocationContext |
| **ADR-0006** (高频地点) | **不影响** — 30 天滚动窗口 + 双 density 独立判定 |

---

## 十、待 v0.2 真接入时的额外配置

| 项 | v0.1 默认 | v0.2 调整 |
|---|---|---|
| `provider` | "mock" | "amap" (改 yaml) |
| `AMAP_API_KEY` | 不需要 | 设置 env var |
| 缓存策略 | 进程内 dict | Redis + TTL (跨服务共享) |
| QPS 限流 | 不限 (demo 量小) | 30 QPS 监控 + 升商业 key |
| 异步查询 | 同步 (demo 小) | path B 候选生成阶段异步 |
| 海外 fallback | "国外" 兜底 | v0.3 加 Google Maps |
