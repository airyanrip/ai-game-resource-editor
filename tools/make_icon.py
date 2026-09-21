"""assets/icon.png, assets/icon.ico 생성 (체크무늬 = 투명, 지워지는 배경을 표현한 도트 감성 아이콘)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets"
N, K = 256, 4  # 최종 크기, 슈퍼샘플링 배율
S = N * K
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=S // 5, fill=(42, 31, 99, 255))                    # 카드
d.rounded_rectangle((S // 16, S // 16, S - S // 16, S - S // 16), radius=S // 6, fill=(26, 18, 64, 255))
# 체크무늬(투명) 영역: 오른쪽 아래에서 왼쪽 위로 '지워지는' 배경
cell = S // 12
x0, y0, x1, y1 = S // 8, S // 8, S - S // 8, S - S // 8
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), radius=S // 10, fill=255)
chk = Image.new("RGBA", (S, S), (0, 0, 0, 0))
cd = ImageDraw.Draw(chk)
for j in range(0, S, cell):
    for i in range(0, S, cell):
        cd.rectangle((i, j, i + cell, j + cell), fill=(255, 255, 255, 255) if (i // cell + j // cell) % 2 == 0 else (200, 194, 236, 255))
tri = Image.new("L", (S, S), 0)
ImageDraw.Draw(tri).polygon([(S, 0), (S, S), (0, S)], fill=255)          # 오른쪽 아래 절반만 체크무늬
green = Image.new("RGBA", (S, S), (0, 200, 90, 255))                       # 왼쪽 위 절반은 초록 배경(아직 안 지운 부분)
base = Image.composite(chk, green, tri)
im.paste(base, (0, 0), mask)
# 주인공(빨간 원)
cx, cy, r = S // 2, S // 2, S // 5
d.ellipse((cx - r - S // 60, cy - r - S // 60, cx + r + S // 60, cy + r + S // 60), fill=(26, 18, 64, 255))
d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(230, 50, 60, 255))
d.ellipse((cx - r // 2, cy - r // 2 - r // 4, cx - r // 8, cy - r // 8), fill=(255, 140, 150, 255))
# 반짝이
def star(x, y, a, color):
    d.polygon([(x, y - a), (x + a // 4, y - a // 4), (x + a, y), (x + a // 4, y + a // 4),
               (x, y + a), (x - a // 4, y + a // 4), (x - a, y), (x - a // 4, y - a // 4)], fill=color)
star(int(S * .78), int(S * .22), S // 9, (255, 200, 61, 255))
star(int(S * .24), int(S * .76), S // 14, (255, 200, 61, 255))
d.rounded_rectangle((S // 16, S // 16, S - S // 16, S - S // 16), radius=S // 6, outline=(255, 200, 61, 255), width=S // 64)
im = im.resize((N, N), Image.LANCZOS)
OUT.mkdir(exist_ok=True)
im.save(OUT / "icon.png")
im.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved", OUT)
