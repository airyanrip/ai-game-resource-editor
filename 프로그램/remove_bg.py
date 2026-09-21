# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""게임 에셋 이미지 배경 자동 투명화 도구.

배경색을 자동 감지(테두리 최빈색)하거나 지정하고, 가장자리에서 이어진 배경 영역만
투명화한다(캐릭터 내부의 같은 색은 보존). 경계는 부드럽게(feather) 처리하고,
배경색이 섞인 테두리 픽셀은 색을 복원(defringe)해 헤일로를 없앤다.

사용:
  uv run remove_bg.py 입력.png [입력2.jpg 폴더 ...] [옵션]
  옵션:
    -o DIR         출력 폴더 (기본: 입력 옆 'transparent' 폴더)
    -t N           색상 허용 오차 0~255 (기본 30)
    -f N           경계 부드러움 폭 (기본 20, 0=하드 엣지)
    -c R,G,B|#hex  배경색 직접 지정 (기본: 자동 감지)
    --global       가장자리 연결 여부와 무관하게 배경색 전부 제거(구멍 포함)
    --trim         투명 여백 잘라내기
    --pad N        --trim 시 남길 여백 px (기본 0)
    -r             폴더 재귀 탐색
    --overwrite    원본 파일명 그대로 같은 위치에 덮어쓰기(PNG 변환)
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga", ".tif", ".tiff", ".gif"}


def parse_color(s):
    s = s.strip().lstrip("#")
    if "," in s:
        r, g, b = (int(v) for v in s.split(","))
    else:
        r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
    return np.array([r, g, b], dtype=np.float32)


def detect_bg(rgb, alpha):
    """테두리 픽셀 중 가장 흔한 색(8단계 양자화 후 평균)을 배경색으로."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    balpha = np.concatenate([alpha[0], alpha[-1], alpha[:, 0], alpha[:, -1]])
    border = border[balpha > 0]
    if len(border) == 0:
        return None
    q = (border // 8).astype(np.int32)
    keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    top = Counter(keys.tolist()).most_common(1)[0][0]
    return border[keys == top].mean(axis=0).astype(np.float32)


def remove_bg(img, tol=30, feather=20, color=None, global_mode=False):
    arr = np.asarray(img.convert("RGBA")).astype(np.float32)
    rgb, a0 = arr[..., :3], arr[..., 3]
    bg = color if color is not None else detect_bg(rgb, a0)
    if bg is None:  # 이미 테두리가 전부 투명
        return img.convert("RGBA")

    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    cand = dist <= tol
    if global_mode:
        removed = cand
    else:
        lab, _ = ndimage.label(cand)  # 4-연결
        edge_labels = np.unique(np.concatenate(
            [lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        edge_labels = edge_labels[edge_labels != 0]
        removed = np.isin(lab, edge_labels)

    alpha = np.where(removed, 0.0, 1.0).astype(np.float32)

    # 경계 처리: 제거 영역 바로 옆 픽셀은 '전경색 + 배경색' 혼합일 수 있다(안티에일리어싱, JPEG).
    # 가장 가까운 확실한 전경 픽셀 색 F를 기준으로 I = a*F + (1-a)*B 를 풀어 알파(a)와 원래 색을 복원한다.
    # 혼합이 아닌 픽셀(예: 외곽선)은 잔차가 커서 그대로 둔다. feather=0이면 알파를 0/1로 자른다.
    iters = 2 + int(feather // 15)
    ring = ndimage.binary_dilation(removed, iterations=iters) & ~removed
    solid = ~removed & ~ring
    if ring.any() and solid.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        ys, xs = np.nonzero(ring)
        fc = rgb[iy[ys, xs], ix[ys, xs]]
        px = rgb[ys, xs]
        d = fc - bg
        den = (d * d).sum(1)
        ok = den > 1.0
        a = np.where(ok, np.clip(((px - bg) * d).sum(1) / np.maximum(den, 1.0), 0, 1), 1.0)
        recon = a[:, None] * fc + (1 - a[:, None]) * bg
        resid = np.sqrt(((px - recon) ** 2).sum(1))
        blend = ok & (resid <= max(20.0, tol))
        recolor = blend & (a < 0.98)  # 혼합 픽셀은 원래(전경) 색으로 복원
        if feather <= 0:
            a = np.where(blend, (a >= 0.5).astype(np.float32), 1.0)
        else:
            a = np.where(blend, a, 1.0)
        new_px = np.where(recolor[:, None], fc, px)
        alpha[ys, xs] = a
        rgb = rgb.copy()
        rgb[ys, xs] = new_px

    out_a = (alpha * a0).round().astype(np.uint8)
    out = np.dstack([rgb.round().astype(np.uint8), out_a])
    return Image.fromarray(out, "RGBA")


def trim(img, pad=0):
    bbox = img.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(l - pad, 0), max(t - pad, 0),
                     min(r + pad, img.width), min(b + pad, img.height)))


def unique_dst(folder, src, used):
    """한 번의 작업 안에서 저장 경로가 겹치지 않게 한다 (hero.png + hero.jpg -> hero.png, hero_jpg.png)."""
    dst = folder / (src.stem + ".png")
    if dst in used:
        dst = folder / f"{src.stem}_{src.suffix.lstrip('.').lower()}.png"
        n = 2
        while dst in used:
            dst = folder / f"{src.stem}_{src.suffix.lstrip('.').lower()}{n}.png"
            n += 1
    used.add(dst)
    return dst


def collect(paths, recursive):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            files += [f for f in it if f.suffix.lower() in EXTS
                      and "transparent" not in f.parent.parts[-1:]]
        elif p.suffix.lower() in EXTS:
            files.append(p)
        else:
            print(f"건너뜀(지원하지 않는 형식): {p}")
    return files


def main():
    ap = argparse.ArgumentParser(description="게임 에셋 배경 자동 투명화")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("-t", "--tolerance", type=float, default=30)
    ap.add_argument("-f", "--feather", type=float, default=20)
    ap.add_argument("-c", "--color")
    ap.add_argument("--global", dest="global_mode", action="store_true")
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    color = parse_color(a.color) if a.color else None
    files = collect(a.inputs, a.recursive)
    if not files:
        print("처리할 이미지가 없습니다.")
        return 1

    ok = 0
    used = set()
    for f in files:
        try:
            if a.overwrite:
                dst = f.with_suffix(".png")
            else:
                d = Path(a.out) if a.out else f.parent / "transparent"
                d.mkdir(parents=True, exist_ok=True)
                dst = unique_dst(d, f, used)
            img = Image.open(f)
            img.load()
            res = remove_bg(img, a.tolerance, a.feather, color, a.global_mode)
            if a.trim:
                res = trim(res, a.pad)
            res.save(dst)
            print(f"OK  {f} -> {dst}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"실패 {f}: {e}")
    print(f"완료: {ok}/{len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
