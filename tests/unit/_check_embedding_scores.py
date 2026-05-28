"""ADR-0019 v0.7: 跑 7 个失败 case 看真 Qwen Embedding 实际分数, 决定阈值调多少."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.mini_album.theme_aggregation import (
    QwenEmbedder, aggregate_theme_clusters, match_theme, truncate_by_relative_threshold,
)
from src.policy.config_loader import load_config

cfg = load_config("theme_aggregation.yaml")["theme_aggregation"]
em = QwenEmbedder()

def show(name, new_tags, album_tags):
    clusters = aggregate_theme_clusters(album_tags, em, merge_similarity=cfg["merge_similarity"])
    clusters = truncate_by_relative_threshold(clusters, cfg["max_clusters"], cfg["relative_threshold"])
    if not clusters:
        print(f"{name:50s} empty clusters"); return
    bt = cfg["band_thresholds"]
    r = match_theme(new_tags, clusters, em, {"strong": bt["strong"], "medium": bt["medium"], "weak": bt["weak"]})
    print(f"{name:50s} score={r.score:.3f} band={r.band}")

# 7 fail cases
print("=== 真 Qwen Embedding 分数实测 ===")
print("当前阈值: strong=0.75 medium=0.55 weak=0.35")
print()
show("[unrelated] zzz_unknown vs lakeside_album", ["zzz_unknown1", "zzz_unknown2"], ["lakeside", "湖边", "湖水"])
show("[unrelated] meal vs lakeside", ["meal", "dish"], ["lakeside", "湖边", "湖水"])
show("[synonym] lakeside vs lakeside_album", ["lakeside", "湖面"], ["lakeside", "湖边", "湖水"])
show("[different] 完全不同 ABC vs DEF", ["apple", "banana"], ["xylophone", "guitar"])
show("[mid] sunset vs lake_album", ["sunset"], ["lakeside", "lake", "water"])
print()
print("=== anchor/theme 不同维度交叉 ===")
show("[main_subjects all diff]", ["a"], ["b", "c", "d"])
