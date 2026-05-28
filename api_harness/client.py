"""后端 3 个 API 的封装 + 轮询/超时 + per-mockBizId 级联删除(API#3)。

参考: SPEC.md §1
- API#1 submit:               mockL1Finish      photoList[{l1Result, photoUrl}] -> {mockBizId, photoMetaIds, userId}
- API#2 result:               mockL1Result      {mockBizId} -> 决策结果(含 photos[].miniAlbumId 等)
- API#3 delete_submission:    mockL1Result/del  {mockBizId} -> 级联删该提交的所有照片+小集(默认实测);
                              后端或有额外配置触发整库 wipe(行为模糊,见 SPEC §1)。
                              runner 用 per-id 账本 teardown,两种模式下都正确。

⚠ 响应包装({code,data,msg} 还是裸 body)与 status/枚举码值尚未确认(SPEC §9),
本模块对包装做容错(_unwrap),轮询判据(_default_done)宽松,首跑由 step1_smoke 观测真实形状。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from api_harness import config


@dataclass
class SubmitResult:
    mock_biz_id: int | None
    photo_meta_ids: list[int]
    user_id: int | None
    raw: dict[str, Any]


def submit(photo_list: list[dict[str, Any]]) -> SubmitResult:
    """API#1 mockL1Finish:提交一批 {l1Result, photoUrl}。"""
    data = _post(config.SUBMIT_URL, {"photoList": photo_list})
    body = _unwrap(data)
    return SubmitResult(
        mock_biz_id=body.get("mockBizId") if isinstance(body, dict) else None,
        photo_meta_ids=(body.get("photoMetaIds") if isinstance(body, dict) else None) or [],
        user_id=body.get("userId") if isinstance(body, dict) else None,
        raw=data,
    )


def fetch_result(mock_biz_id: int) -> dict[str, Any]:
    """API#2 mockL1Result:取一次结果(不轮询)。返回原始响应。"""
    return _post(config.RESULT_URL, {"mockBizId": mock_biz_id})


def poll_result(
    mock_biz_id: int,
    *,
    is_done: Callable[[dict], bool] | None = None,
    interval: float | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """轮询 API#2 直到 done 或超时。超时也返回最后一次,交调用方判。"""
    interval = interval or config.POLL_INTERVAL_S
    timeout = timeout or config.POLL_TIMEOUT_S
    deadline = time.monotonic() + timeout
    done = is_done or _default_done
    last: dict[str, Any] = {}
    while True:
        last = fetch_result(mock_biz_id)
        if done(_unwrap(last)):
            return last
        if time.monotonic() >= deadline:
            return last
        time.sleep(interval)


def delete_submission(mock_biz_id: int) -> dict[str, Any]:
    """API#3 mockL1Result/del:**按 mockBizId 级联删除该次提交**(默认实测,SPEC §1)。

    级联删 mockBizId 对应的所有照片 + 该提交形成的小集。
    ⚠ 行为存在两种模式:
      - 默认观测(2026-05-28 实测):per-id 级联(`del(X)` 不动其他提交)。
      - 后端或有额外配置触发整库 wipe(此时调任意 id 都会清全库)。
    runner 取 per-id 账本 teardown,在两种模式下都正确。
    """
    return _post(config.DELETE_URL, {"mockBizId": mock_biz_id})


#: 兼容旧调用名(step1_smoke / 历史代码);新代码请用 delete_submission / wipe_db。
delete = delete_submission
#: 兼容 v0.8 短暂存在的 wipe 命名(默认行为是 per-id 级联,SPEC §1)。
wipe_db = delete_submission


# ── 内部 ────────────────────────────────────────────────────────────────

#: dev 服务器 TLS 间歇性 EOF / 连接重置 → 对网络层错误重试(非 HTTP 4xx/5xx)。
_NET_RETRIES = 3
_NET_BACKOFF_S = 1.0


def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, _NET_RETRIES + 1):
        try:
            resp = requests.post(
                url, json=payload, headers=config.default_headers(),
                params=config.default_params(),
                timeout=config.REQUEST_TIMEOUT_S,
            )
            break
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt < _NET_RETRIES:
                time.sleep(_NET_BACKOFF_S * attempt)
    else:  # 重试用尽仍网络错
        raise last_exc  # type: ignore[misc]
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return {}
    try:
        return resp.json()
    except ValueError:
        return {"_raw_text": text}


def _unwrap(data: Any) -> dict[str, Any]:
    """后端若包了 {code,data,msg},取 data;否则原样。"""
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data if isinstance(data, dict) else {}


#: 非终态(轮询时继续等)。实测 status: PROCESSING(算法处理中)→ 终态。
_PENDING_STATUS = {"PROCESSING", "INIT", "PENDING", "RUNNING", "QUEUED", ""}


def _default_done(body: dict[str, Any]) -> bool:
    """完成判据:status 非空且不在 PENDING 集合即视为终态。

    实测(2026-05-27):PROCESSING=处理中;NOT_FOUND=已删除(终态);终态决策值待观测。
    """
    status = str(body.get("status", "")).upper()
    return bool(status) and status not in _PENDING_STATUS
