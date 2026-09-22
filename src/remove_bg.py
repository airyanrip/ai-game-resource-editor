# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""AI 게임 리소스 편집기 - 배경 자동 투명화 · 크기 조절 · 자르기 · 위치 조절 엔진 (+ 명령줄 도구).

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
    --pad N        --trim 시 피사체 둘레에 남길 투명 여백 px (기본 0)
    --crop L,T,R,B 왼쪽,위,오른쪽,아래에서 잘라낼 % (배경 제거 직후, 여백 자르기 전)
    --scale PCT    배율 % (200 = 2배 업스케일, 50 = 절반)
    --size WxH     목표 크기 px (기본은 비율 유지, 한쪽만: 512x0)   --stretch 비율 무시
    --method M     nearest(또렷·도트) | smooth(부드럽게, 기본) | sharp(선명하게)
    --canvas WxH   고정 캔버스 크기 (피사체를 이 안에 배치)
    --align P      캔버스 안 정렬: tl tc tr / ml c mr / bl bc br (기본 c)
    --offset DX,DY 캔버스 안 위치 이동 px      --margin N 캔버스 안쪽 여백 px
    --fit          피사체를 캔버스(여백 제외)에 맞춰 자동 조정
    -r             폴더 재귀 탐색
    --overwrite    원본 파일명 그대로 같은 위치에 덮어쓰기(PNG 변환)
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
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


def _alpha_bbox(img):
    return img.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()


def trim(img, pad=0):
    """투명 여백을 잘라내고, 피사체 둘레에 투명 여백 pad px를 남긴다."""
    bbox = _alpha_bbox(img)
    if not bbox:
        return img
    out = img.crop(bbox)
    if pad > 0:
        framed = Image.new("RGBA", (out.width + 2 * pad, out.height + 2 * pad), (0, 0, 0, 0))
        framed.paste(out, (pad, pad))
        out = framed
    return out


# ---------------------------------------------------------------- 크기 · 위치 · 자르기
ALIGNS = {"tl": (0, 0), "tc": (1, 0), "tr": (2, 0), "ml": (0, 1), "c": (1, 1), "mr": (2, 1),
          "bl": (0, 2), "bc": (1, 2), "br": (2, 2)}


def default_opts():
    return dict(
        crop=(0, 0, 0, 0),      # 왼쪽/위/오른쪽/아래에서 잘라낼 % (0~50)
        trim=False, pad=0,      # 투명 여백 자르기 + 남길 여백 px
        resize="none",          # none | scale(배율 %) | size(가로x세로 px)
        scale=100, size=(0, 0), keep_ratio=True,
        method="smooth",        # nearest(또렷/도트) | smooth(부드럽게) | sharp(선명하게)
        canvas=None,            # (가로, 세로) 고정 캔버스. None이면 피사체 크기 그대로
        fit=False,              # 캔버스(여백 제외)에 맞춰 크기 자동 조정
        align=(1, 1),           # 캔버스 안 정렬 (0/1/2 = 왼쪽·가운데·오른쪽, 위·가운데·아래)
        offset=(0, 0), margin=0,
    )


def _resample(img, size, method):
    size = (max(1, int(round(size[0]))), max(1, int(round(size[1]))))
    if size == img.size:
        return img
    if method == "nearest":
        return img.resize(size, Image.NEAREST)
    # 알파 미리곱(RGBa)으로 크기를 바꿔야 투명 경계에 검은/흰 테두리가 생기지 않는다.
    out = img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
    if method == "sharp":
        rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=2))
        out = Image.merge("RGBA", (*rgb.split(), out.getchannel("A")))
    return out


def _paste_rgba(canvas, img, x, y):
    """canvas 밖으로 나가는 부분은 잘라내고, 알파를 올바르게 합성해 붙인다."""
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + img.width, canvas.width), min(y + img.height, canvas.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(img.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def postprocess(img, o, ref=1.0):
    """배경 제거 후 처리: 자르기 -> 여백 자르기 -> 크기 조절 -> 캔버스/위치.

    ref: px 단위 옵션(여백·크기·캔버스·이동)에 곱할 배율. 축소된 미리보기 이미지에 같은 결과를
    보여줄 때 (미리보기 너비 / 원본 너비)를 넣는다.
    """
    img = img.convert("RGBA")
    cl, ct, cr, cb = o["crop"]
    if any((cl, ct, cr, cb)):
        w, h = img.size
        box = (int(w * cl / 100), int(h * ct / 100), w - int(w * cr / 100), h - int(h * cb / 100))
        if box[2] - box[0] >= 1 and box[3] - box[1] >= 1:
            img = img.crop(box)
    if o["trim"]:
        img = trim(img, int(round(o["pad"] * ref)))

    method = o["method"]
    if o["resize"] == "scale" and o["scale"] != 100:
        f = o["scale"] / 100
        img = _resample(img, (img.width * f, img.height * f), method)
    elif o["resize"] == "size":
        tw, th = o["size"][0] * ref, o["size"][1] * ref
        if tw > 0 or th > 0:
            if o["keep_ratio"] or tw <= 0 or th <= 0:
                f = min(v for v in ((tw / img.width) if tw > 0 else None,
                                    (th / img.height) if th > 0 else None) if v is not None)
                new = (img.width * f, img.height * f)
            else:
                new = (tw, th)
            img = _resample(img, new, method)

    if o["canvas"]:
        cw, ch = (max(1, int(round(v * ref))) for v in o["canvas"])
        mg = o["margin"] * ref
        if o["fit"]:
            f = min((cw - 2 * mg) / img.width, (ch - 2 * mg) / img.height)
            if f > 0:
                img = _resample(img, (img.width * f, img.height * f), method)
        ax, ay = o["align"]
        x = int(round(mg + ax / 2 * (cw - 2 * mg - img.width) + o["offset"][0] * ref))
        y = int(round(mg + ay / 2 * (ch - 2 * mg - img.height) + o["offset"][1] * ref))
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        _paste_rgba(canvas, img, x, y)
        img = canvas
    return img


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
    ap = argparse.ArgumentParser(description="AI 게임 리소스 편집기: 배경 투명화 · 크기 조절 · 자르기 · 위치 조절")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("-t", "--tolerance", type=float, default=30)
    ap.add_argument("-f", "--feather", type=float, default=20)
    ap.add_argument("-c", "--color")
    ap.add_argument("--global", dest="global_mode", action="store_true")
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--crop", help="왼쪽,위,오른쪽,아래에서 잘라낼 %% (예: 10,0,10,5)")
    ap.add_argument("--scale", type=float, help="배율 %% (예: 200 = 2배 업스케일)")
    ap.add_argument("--size", help="목표 크기 가로x세로 px (예: 512x512, 한쪽만 주려면 512x0)")
    ap.add_argument("--stretch", action="store_true", help="--size 에서 비율을 무시하고 꽉 채움")
    ap.add_argument("--method", choices=["nearest", "smooth", "sharp"], default="smooth",
                    help="크기 조절 방식: nearest=또렷(도트), smooth=부드럽게, sharp=선명하게")
    ap.add_argument("--canvas", help="고정 캔버스 크기 가로x세로 px (예: 256x256)")
    ap.add_argument("--align", choices=sorted(ALIGNS), default="c",
                    help="캔버스 안 정렬 (tl tc tr ml c mr bl bc br)")
    ap.add_argument("--offset", help="캔버스 안 위치 이동 dx,dy px (예: 0,-8)")
    ap.add_argument("--margin", type=int, default=0, help="캔버스 안쪽 여백 px")
    ap.add_argument("--fit", action="store_true", help="피사체를 캔버스(여백 제외)에 맞춰 자동 조정")
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    def pair(name, s, sep):
        try:
            x, y = s.lower().split(sep)
            return float(x), float(y)
        except ValueError:
            ap.error(f"{name} 값 형식이 잘못됐어요: '{s}' (예: 가로{sep}세로 → 512{sep}512)")

    opts = default_opts()
    opts.update(trim=a.trim, pad=a.pad, method=a.method, keep_ratio=not a.stretch,
                fit=a.fit, margin=a.margin, align=ALIGNS[a.align])
    if a.crop:
        try:
            crop = tuple(float(v) for v in a.crop.split(","))
            assert len(crop) == 4
        except (ValueError, AssertionError):
            ap.error(f"--crop 값 형식이 잘못됐어요: '{a.crop}' (예: 10,0,10,5 = 왼쪽,위,오른쪽,아래 %)")
        opts["crop"] = crop
    if a.scale:
        opts.update(resize="scale", scale=a.scale)
    if a.size:
        opts.update(resize="size", size=pair("--size", a.size, "x"))
    if a.canvas:
        opts["canvas"] = tuple(int(v) for v in pair("--canvas", a.canvas, "x"))
    if a.offset:
        opts["offset"] = pair("--offset", a.offset, ",")

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
            res = postprocess(res, opts)
            res.save(dst)
            print(f"OK  {f} -> {dst}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"실패 {f}: {e}")
    print(f"완료: {ok}/{len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
