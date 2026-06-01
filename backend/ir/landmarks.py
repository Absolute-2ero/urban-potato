from __future__ import annotations

from typing import Optional


LANDMARKS: dict[str, tuple[float, float]] = {
    # Beijing — commercial / expat
    "sanlitun":              (39.9333, 116.4544),
    "guomao":                (39.9082, 116.4632),
    "cbd":                   (39.9082, 116.4632),
    "chaoyang":              (39.9217, 116.4434),
    "chaoyang park":         (39.9369, 116.4733),
    "wangfujing":            (39.9145, 116.4082),
    "xidan":                 (39.9130, 116.3744),
    "dongzhimen":            (39.9389, 116.4358),
    "liangmaqiao":           (39.9506, 116.4610),
    "solana":                (39.9600, 116.4740),
    "taikoo li":             (39.9333, 116.4544),
    # Beijing — universities
    "wudaokou":              (40.0023, 116.3394),
    "tsinghua":              (40.0038, 116.3225),
    "tsinghua university":   (40.0038, 116.3225),
    "beida":                 (39.9995, 116.3051),
    "peking university":     (39.9995, 116.3051),
    "pku":                   (39.9995, 116.3051),
    "renmin university":     (39.9652, 116.3176),
    "ruc":                   (39.9652, 116.3176),
    "uibe":                  (39.9611, 116.4418),
    # Beijing — districts / hubs
    "zhongguancun":          (39.9839, 116.3136),
    "haidian":               (40.0082, 116.2985),
    "dongcheng":             (39.9376, 116.4155),
    "xicheng":               (39.9137, 116.3606),
    # Chinese names — Beijing
    "三里屯":                  (39.9333, 116.4544),
    "国贸":                    (39.9082, 116.4632),
    "朝阳":                    (39.9217, 116.4434),
    "朝阳公园":                  (39.9369, 116.4733),
    "王府井":                   (39.9145, 116.4082),
    "西单":                    (39.9130, 116.3744),
    "五道口":                   (40.0023, 116.3394),
    "清华":                    (40.0038, 116.3225),
    "清华大学":                  (40.0038, 116.3225),
    "北大":                    (39.9995, 116.3051),
    "北京大学":                  (39.9995, 116.3051),
    "人民大学":                  (39.9652, 116.3176),
    "中关村":                   (39.9839, 116.3136),
    "海淀":                    (40.0082, 116.2985),
    "东城":                    (39.9376, 116.4155),
    "西城":                    (39.9137, 116.3606),
    # HK — English
    "central":               (22.2820, 114.1588),
    "causeway bay":          (22.2801, 114.1841),
    "mong kok":              (22.3193, 114.1694),
    "mongkok":               (22.3193, 114.1694),
    "tsim sha tsui":         (22.2975, 114.1722),
    "tst":                   (22.2975, 114.1722),
    "wan chai":              (22.2793, 114.1722),
    "wanchai":               (22.2793, 114.1722),
    "admiralty":             (22.2793, 114.1650),
    "sheung wan":            (22.2860, 114.1511),
    "north point":           (22.2910, 114.1910),
    "quarry bay":            (22.2860, 114.2110),
    "taikoo":                (22.2840, 114.2160),
    "jordan":                (22.3051, 114.1718),
    "yau ma tei":            (22.3130, 114.1690),
    "kowloon city":          (22.3282, 114.1915),
    "sham shui po":          (22.3310, 114.1610),
    "kwun tong":             (22.3113, 114.2262),
    "sha tin":               (22.3771, 114.1895),
    # HK — Chinese names
    "中环":                    (22.2820, 114.1588),
    "铜锣湾":                   (22.2801, 114.1841),
    "旺角":                    (22.3193, 114.1694),
    "尖沙咀":                   (22.2975, 114.1722),
    "湾仔":                    (22.2793, 114.1722),
    "上环":                    (22.2860, 114.1511),
    "北角":                    (22.2910, 114.1910),
    "太古":                    (22.2840, 114.2160),
    "九龙城":                   (22.3282, 114.1915),
    "深水埗":                   (22.3310, 114.1610),
    "观塘":                    (22.3113, 114.2262),
    "沙田":                    (22.3771, 114.1895),
}


def find_landmark(tokens: list[str]) -> Optional[tuple[str, tuple[float, float]]]:
    """Try n-gram combinations (3→1 tokens) against the landmark dict."""
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n]).lower()
            if phrase in LANDMARKS:
                return phrase, LANDMARKS[phrase]
    return None
