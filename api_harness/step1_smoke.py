"""Step 1 冒烟:打通「提交 → 轮询取结果 → 删除」最小链路,并实测删除行为 + 摸枚举码值。

跑法(项目根目录):
    python -m api_harness.step1_smoke

参考: SPEC.md §10 Step 1。本脚本不依赖 src/,只调后端 3 个 API。
故意造 3 张同主题(食物)照片 → 期望成集 → 拿 miniAlbumId → 删除 → 复查残留,
顺便把 status / route / displayDecisionCode / associationStrength 等真实码值打出来。
"""
from __future__ import annotations

import copy
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from api_harness import client, config

REF = Path(__file__).resolve().parent / "reference" / "l1_standard_sample.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _build_photos() -> list[dict[str, Any]]:
    """3 张同主题(食物/室内)照片,ai_scene_tags 一致 → 期望成集。"""
    base = json.loads(REF.read_text(encoding="utf-8"))
    variants = [
        ("刚出笼的小笼包", ["小笼包", "蒸笼", "筷子"]),
        ("热汤面一碗", ["汤面", "青菜", "瓷碗"]),
        ("桌上的家常菜", ["红烧肉", "米饭", "瓷盘"]),
    ]
    photos = []
    for i, (title, subjects) in enumerate(variants, 1):
        l1 = copy.deepcopy(base)
        l1["individual_title"] = title
        l1["salient_objects"] = subjects                 # B 桶:salient_objects ← main_subjects
        l1["semantic_facts"]["main_subjects"] = subjects
        # ai_scene_tags 保持一致(食物/室内)→ 同主题
        photos.append({"l1Result": l1, "photoUrl": f"https://example.com/mock/food_{i}.jpg"})
    return photos


def main() -> None:
    print("=" * 70)
    print(f"Step 1 冒烟 · {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"BASE_URL = {config.BASE_URL}")
    print("=" * 70)

    photos = _build_photos()
    print(f"\n[1] 提交 {len(photos)} 张同主题(食物)照片 → API#1 mockL1Finish ...")
    sub = client.submit(photos)
    print("  submit 原始响应:")
    print("  " + _dump(sub.raw).replace("\n", "\n  "))
    print(f"  → mockBizId={sub.mock_biz_id}  photoMetaIds={sub.photo_meta_ids}  userId={sub.user_id}")

    if sub.mock_biz_id is None:
        print("\n✗ 没拿到 mockBizId,响应包装可能和假设不同。看上面原始响应调整 client._unwrap。")
        return

    print(f"\n[2] 轮询 → API#2 mockL1Result(mockBizId={sub.mock_biz_id}) ...")
    result = client.poll_result(sub.mock_biz_id)
    print("  result 原始响应:")
    print("  " + _dump(result).replace("\n", "\n  "))

    body = client._unwrap(result)
    print("\n  —— 关键字段速览(摸码值)——")
    for k in ("status", "route", "displayDecision", "displayDecisionCode", "displayDecisionDesc", "nextFlowCode"):
        print(f"    {k:22} = {body.get(k)!r}")
    album_ids = set()
    for i, p in enumerate(body.get("photos") or [], 1):
        mid = p.get("miniAlbumId")
        if mid:
            album_ids.add(mid)
        print(f"    photo#{i}: miniAlbumId={mid!r} decisionTierCode={p.get('decisionTierCode')!r} "
              f"associationStrength={p.get('associationStrength')!r} truthTablePattern={p.get('truthTablePattern')!r} "
              f"finalResultCode={p.get('finalResultCode')!r}")
    print(f"  → 形成的小集 miniAlbumId 集合: {album_ids or '（无,可能没成集)'}")

    _save("submit_and_result", {"submit": sub.raw, "result": result})

    print(f"\n[3] 删除 → API#3 mockL1Result/del(mockBizId={sub.mock_biz_id}) ...")
    del_resp = client.delete(sub.mock_biz_id)
    print("  delete 原始响应:")
    print("  " + _dump(del_resp).replace("\n", "\n  "))

    print("\n[4] 删除后复查 → 再调 API#2 看是否还有数据 ...")
    time.sleep(1.0)
    after = client.fetch_result(sub.mock_biz_id)
    print("  复查响应:")
    print("  " + _dump(after).replace("\n", "\n  "))
    after_body = client._unwrap(after)
    after_album_ids = {p.get("miniAlbumId") for p in (after_body.get("photos") or []) if p.get("miniAlbumId")}

    _save("delete_and_recheck", {"delete": del_resp, "recheck": after})

    print("\n" + "=" * 70)
    print("链路结论:")
    print(f"  提交 → 轮询 → 删除 三步均完成(HTTP 未抛错)。")
    print(f"  成集 miniAlbumId(删前): {album_ids or '无'}")
    print(f"  删后复查仍残留的 miniAlbumId: {after_album_ids or '无'}")
    # API#3 = 整库清空(后端 2026-05-28 确认)。wipe 后整库应空。
    if not after_album_ids:
        print("  ✓ wipe 后整库已空(status=NOT_FOUND / photos=[])→ 整库清空生效,隔离干净。")
    else:
        print("  ⚠ wipe 后仍有残留小集 → 与「整库清空」不符,回报 Ace 核实后端。")
    print("=" * 70)


def _save(tag: str, payload: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"step1_{tag}_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(_dump(payload), encoding="utf-8")
    print(f"  (raw 已存 {path.relative_to(path.parents[2])})")


if __name__ == "__main__":
    main()
