# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy", "scipy", "tkinterdnd2"]
# ///
"""AI 게임 리소스 편집기 GUI (게임 스타일). exe 빌드는 build_exe.bat.

- 창 크기에 맞춰 UI 전체가 비율대로 커지고 작아진다 (크기 조절이 멈추면 다시 그림)
- 설정: 언어(한국어/English/日本語/中文), 캐시 정리, 자동 저장 경로
"""
import json
import os
import queue
import shutil
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageTk
import remove_bg as rb

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    Root = TkinterDnD.Tk
except Exception:  # 드래그앤드롭 없이도 동작
    DND_FILES = None
    Root = tk.Tk

# ---- 경로 ----
# exe(PyInstaller)로 실행하면: 번들 리소스는 임시 폴더(_MEIPASS), 설정/캐시는 exe 옆에 둔다.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BUNDLE_DIR = Path(sys._MEIPASS)
    ROOT_DIR = Path(sys.executable).resolve().parent
    PROG_DIR = ROOT_DIR
else:
    PROG_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = ROOT_DIR = PROG_DIR.parent
FONT_DIR = BUNDLE_DIR / "fonts"
ASSET_DIR = BUNDLE_DIR / "assets"
SETTINGS_PATH = ROOT_DIR / "settings.json"
LOG_PATH = ROOT_DIR / "error_log.txt"
CACHE_ITEMS = [ROOT_DIR / "cache", LOG_PATH] + ([] if FROZEN else [PROG_DIR / "__pycache__"])

# ---- 팔레트 ----
BG = "#1a1240"
PANEL = "#2a1f63"
PANEL_HI = "#4a3a9a"
DARK = "#120c2e"
GOLD = "#ffc83d"
GOLD_D = "#d99a12"
PINK = "#ff5c93"
PINK_D = "#c93468"
MINT = "#3fe0b0"
MINT_D = "#1fa982"
SKY = "#5cb8ff"
SKY_D = "#2f83c9"
TEXT = "#ffffff"
SUB = "#b9aee8"
INACTIVE = "#3b2f85"
INACTIVE_D = "#251b5c"

PV_W, PV_H = 270, 190   # 미리보기 칸 기준 크기 (배율 1.0)
LEFT_W = 330            # 왼쪽 열 기준 너비
TAB_H = 148             # 오른쪽 카드의 탭 내용 영역 기준 높이
PREVIEW_WORK = 640      # 미리보기 계산용 이미지의 긴 변 최대 px
MAX_PX = 8192           # 크기·캔버스 입력 상한 (메모리 보호)
S = 1.0                 # 현재 배율 (창 크기에 따라 바뀜)


def sc(n):
    """기준(배율 1.0) 픽셀 -> 현재 배율 픽셀"""
    return max(1, int(round(n * S)))


# ---- 도트 폰트 (갈무리, OFL) : 설치 없이 이 프로그램에서만 사용 ----
PIXEL = False
if sys.platform == "win32":
    try:
        import ctypes
        for _name in ("Galmuri11.ttf", "Galmuri14.ttf"):
            # 0x10 = FR_PRIVATE (이 프로세스에서만 유효)
            PIXEL = ctypes.windll.gdi32.AddFontResourceExW(str(FONT_DIR / _name), 0x10, 0) > 0 or PIXEL
    except Exception:
        PIXEL = False

_FAM = {}


def _family(key):
    """설치된 글꼴 이름 중 갈무리를 찾는다 (윈도우에서는 'Galmuri11 Regular'로 등록됨)."""
    if key not in _FAM:
        names = [n for n in tkfont.families() if n.lstrip("@").startswith(key)]
        _FAM[key] = min(names, key=len) if names else None
    return _FAM[key]


def F(size, bold=True):
    """size는 기존 pt 기준 크기. 배율(S)에 맞춰 커진다."""
    if PIXEL:
        if size <= 10:
            fam, px = _family("Galmuri11"), 11
        elif size <= 13:
            fam, px = _family("Galmuri14"), 14
        elif size <= 18:
            fam, px = _family("Galmuri11"), 22
        else:
            fam, px = _family("Galmuri11"), 33
        if fam:
            px = max(8, int(round(px * S)))
            return (fam, -px, "bold") if bold and px > 11 else (fam, -px)
    return ("맑은 고딕", max(7, int(round(size * S))), "bold" if bold else "normal")


def shade(hex_color, k):
    c = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * k))) for v in c)


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def checker(size, cell):
    im = Image.new("RGB", size, (255, 255, 255))
    px = im.load()
    for y in range(size[1]):
        for x in range(size[0]):
            if (x // cell + y // cell) % 2:
                px[x, y] = (214, 208, 240)
    return im


# ======================================================================
# 번역
# ======================================================================
LANGS = [("ko", "한국어"), ("en", "English"), ("ja", "日本語"), ("zh", "中文")]

T = {
    "ko": {
        "win_title": "AI 게임 리소스 편집기",
        "title": "✦ AI 게임 리소스 편집기 ✦",
        "subtitle": "배경 제거부터 크기·위치 편집까지 한 번에!",
        "settings": "⚙ 설정",
        "sec1": "이미지 담기", "sec2": "미리보기 · 조절", "sec3": "저장하기",
        "btn_images": "▣ 이미지", "btn_folder": "▶ 폴더", "btn_clear": "✖ 비우기",
        "hint_dnd": "▼ 여기에 파일·폴더를 끌어다 놓아도 돼요",
        "hint_nodnd": "버튼으로 이미지를 선택하세요",
        "orig": "원본", "result": "결과 (체크무늬 = 투명)", "placeholder": "이미지를\n담아주세요",
        "tol_name": "배경 지우기 강도", "tol_tip": "배경이 남으면 ▲ 올리고, 그림이 깎이면 ▼ 내리세요",
        "fea_name": "경계 부드러움", "fea_tip": "0 = 또렷하게 (도트 그래픽 추천)",
        "bg_color": "배경색", "auto_detect": "자동 감지", "pick_color": "◆ 직접 고르기", "auto": "↻ 자동",
        "trim": "투명 여백 잘라내기", "glob": "그림 안쪽 같은 색도 지우기",
        "save_to": "저장 위치: {p}", "save_default": "원본 옆 'transparent' 폴더",
        "change_save": "▶ 저장 위치 바꾸기",
        "start": "✦  투명화 시작!  ✦", "working": "✦  처리 중…  ✦",
        "st_empty": "이미지를 담아주세요!",
        "st_ready": "✔ {n}개 이미지 준비 완료! 아래 버튼을 눌러보세요",
        "st_work": "마법 부리는 중… {i}/{n}",
        "st_done": "★ 완료! {ok}개 성공", "st_fail": ", {f}개 실패",
        "st_preview_fail": "미리보기 실패: {e}",
        "warn_title": "알림", "warn_empty": "먼저 이미지를 담아주세요!",
        "done_title": "완료", "done_msg": "{ok}개 저장 완료!\n\n저장 위치:\n{d}",
        "done_none": "저장된 파일이 없습니다.", "done_fails": "실패:", "open_q": "저장 폴더를 열까요?",
        "err_title": "실패",
        "dlg_images": "이미지 선택", "dlg_all": "모든 파일", "dlg_img_type": "이미지",
        "dlg_folder": "폴더 선택 (하위 폴더 포함)", "dlg_out": "저장할 폴더", "dlg_color": "배경색 선택",
        "set_title": "설정",
        "set_lang": "언어 / Language",
        "set_cache": "캐시 정리",
        "set_cache_info": "임시 파일 크기: {s}\n(오류 기록·임시 파일. 원본과 결과 이미지는 지워지지 않아요)",
        "set_cache_btn": "✖ 캐시 정리하기",
        "set_cache_done": "{s}를 정리했어요!",
        "set_save": "자동 저장 경로",
        "set_current": "현재 경로:",
        "set_change": "▶ 변경", "set_reset": "↻ 기본값(원본 옆)", "set_open": "▣ 폴더 열기",
        "set_close": "닫기",
        "set_saved": "설정은 자동으로 저장돼요",
        # 크기 · 업스케일 · 자르기 · 위치
        "tab_bg": "배경", "tab_size": "크기·업스케일", "tab_crop": "자르기", "tab_pos": "위치",
        "rz_none": "사용 안 함", "rz_scale": "배율로", "rz_size": "크기 지정",
        "sc_name": "배율", "sc_size": "크기", "keep_ratio": "비율 유지",
        "method": "방식", "m_nearest": "또렷하게(도트)", "m_smooth": "부드럽게", "m_sharp": "선명하게",
        "pad_name": "남길 여백",
        "crop_drag_hint": "◆ 왼쪽 원본 그림 위의 상자를 끌어 잘라낼 범위를 정하세요 (모서리 = 크기, 안쪽 = 이동)",
        "crop_reset": "↻ 전체 이미지로",
        "crop_hint": "자르기는 배경을 지운 직후에, '투명 여백 잘라내기'는 그다음에 적용돼요.",
        "cv_use": "캔버스 사용", "cv_fit": "크기 맞춤",
        "off_x": "가로 이동", "off_y": "세로 이동", "margin": "안쪽 여백",
        "size_info": "원본 {ow}×{oh}px  ➜  결과 {w}×{h}px",
    },
    "en": {
        "win_title": "AI Game Resource Editor",
        "title": "✦ AI Game Resource Editor ✦",
        "subtitle": "From background removal to resize & positioning, all in one!",
        "settings": "⚙ Settings",
        "sec1": "Add Images", "sec2": "Preview & Adjust", "sec3": "Save",
        "btn_images": "▣ Images", "btn_folder": "▶ Folder", "btn_clear": "✖ Clear",
        "hint_dnd": "▼ You can also drag & drop files or folders here",
        "hint_nodnd": "Use the buttons to pick images",
        "orig": "Original", "result": "Result (checker = transparent)", "placeholder": "Add an\nimage",
        "tol_name": "Erase strength", "tol_tip": "Raise if background remains, lower if the art gets cut",
        "fea_name": "Edge softness", "fea_tip": "0 = crisp (best for pixel art)",
        "bg_color": "BG color", "auto_detect": "Auto detect", "pick_color": "◆ Pick color", "auto": "↻ Auto",
        "trim": "Trim transparent margin", "glob": "Also erase same color inside",
        "save_to": "Save to: {p}", "save_default": "next to the original ('transparent' folder)",
        "change_save": "▶ Change save folder",
        "start": "✦  REMOVE BG!  ✦", "working": "✦  Working…  ✦",
        "st_empty": "Add some images!",
        "st_ready": "✔ {n} image(s) ready! Press the big button below",
        "st_work": "Casting magic… {i}/{n}",
        "st_done": "★ Done! {ok} succeeded", "st_fail": ", {f} failed",
        "st_preview_fail": "Preview failed: {e}",
        "warn_title": "Notice", "warn_empty": "Please add images first!",
        "done_title": "Done", "done_msg": "{ok} file(s) saved!\n\nSaved to:\n{d}",
        "done_none": "No files were saved.", "done_fails": "Failed:", "open_q": "Open the save folder?",
        "err_title": "Failed",
        "dlg_images": "Select images", "dlg_all": "All files", "dlg_img_type": "Images",
        "dlg_folder": "Select a folder (subfolders included)", "dlg_out": "Folder to save into",
        "dlg_color": "Pick background color",
        "set_title": "Settings",
        "set_lang": "Language / 언어",
        "set_cache": "Clear cache",
        "set_cache_info": "Temp file size: {s}\n(error log & temp files. Your images are never deleted)",
        "set_cache_btn": "✖ Clear cache",
        "set_cache_done": "Cleared {s}!",
        "set_save": "Auto-save folder",
        "set_current": "Current:",
        "set_change": "▶ Change", "set_reset": "↻ Default (next to original)", "set_open": "▣ Open folder",
        "set_close": "Close",
        "set_saved": "Settings are saved automatically",
        "tab_bg": "Background", "tab_size": "Resize/Upscale", "tab_crop": "Crop", "tab_pos": "Position",
        "rz_none": "Off", "rz_scale": "By scale", "rz_size": "By size",
        "sc_name": "Scale", "sc_size": "Size", "keep_ratio": "Keep ratio",
        "method": "Method", "m_nearest": "Crisp (pixel art)", "m_smooth": "Smooth", "m_sharp": "Sharp",
        "pad_name": "Keep margin",
        "crop_drag_hint": "◆ Drag the box on the original image (left) to pick what to keep (corners = resize, inside = move)",
        "crop_reset": "↻ Full image",
        "crop_hint": "Crop is applied right after the background is removed; 'Trim transparent margin' comes next.",
        "cv_use": "Use canvas", "cv_fit": "Fit to canvas",
        "off_x": "Move X", "off_y": "Move Y", "margin": "Inner margin",
        "size_info": "Original {ow}×{oh}px  ➜  Result {w}×{h}px",
    },
    "ja": {
        "win_title": "AIゲームリソースエディター",
        "title": "✦ AIゲームリソースエディター ✦",
        "subtitle": "背景除去からサイズ・位置の編集まで、まとめて!",
        "settings": "⚙ 設定",
        "sec1": "画像を入れる", "sec2": "プレビュー・調整", "sec3": "保存",
        "btn_images": "▣ 画像", "btn_folder": "▶ フォルダ", "btn_clear": "✖ クリア",
        "hint_dnd": "▼ ファイルやフォルダをここにドラッグしてもOK",
        "hint_nodnd": "ボタンで画像を選んでください",
        "orig": "元画像", "result": "結果 (チェック柄 = 透明)", "placeholder": "画像を\n入れてね",
        "tol_name": "消去の強さ", "tol_tip": "背景が残ったら上げ、絵が欠けたら下げてください",
        "fea_name": "境界のなめらかさ", "fea_tip": "0 = くっきり (ドット絵向け)",
        "bg_color": "背景色", "auto_detect": "自動検出", "pick_color": "◆ 色を選ぶ", "auto": "↻ 自動",
        "trim": "透明な余白を切り取る", "glob": "絵の中の同じ色も消す",
        "save_to": "保存先: {p}", "save_default": "元画像の隣 ('transparent' フォルダ)",
        "change_save": "▶ 保存先を変更",
        "start": "✦  透明化スタート!  ✦", "working": "✦  処理中…  ✦",
        "st_empty": "画像を入れてください!",
        "st_ready": "✔ {n}枚の画像が準備できました! 下のボタンを押してね",
        "st_work": "魔法をかけ中… {i}/{n}",
        "st_done": "★ 完了! {ok}枚 成功", "st_fail": "、{f}枚 失敗",
        "st_preview_fail": "プレビュー失敗: {e}",
        "warn_title": "お知らせ", "warn_empty": "先に画像を入れてください!",
        "done_title": "完了", "done_msg": "{ok}枚 保存しました!\n\n保存先:\n{d}",
        "done_none": "保存されたファイルはありません。", "done_fails": "失敗:", "open_q": "保存フォルダを開きますか?",
        "err_title": "失敗",
        "dlg_images": "画像を選択", "dlg_all": "すべてのファイル", "dlg_img_type": "画像",
        "dlg_folder": "フォルダを選択 (サブフォルダ含む)", "dlg_out": "保存するフォルダ",
        "dlg_color": "背景色を選択",
        "set_title": "設定",
        "set_lang": "言語 / Language",
        "set_cache": "キャッシュ削除",
        "set_cache_info": "一時ファイルのサイズ: {s}\n(エラーログ・一時ファイル。画像は削除されません)",
        "set_cache_btn": "✖ キャッシュを削除",
        "set_cache_done": "{s}を削除しました!",
        "set_save": "自動保存先",
        "set_current": "現在の保存先:",
        "set_change": "▶ 変更", "set_reset": "↻ 初期値(元画像の隣)", "set_open": "▣ フォルダを開く",
        "set_close": "閉じる",
        "set_saved": "設定は自動で保存されます",
        "tab_bg": "背景", "tab_size": "サイズ・拡大", "tab_crop": "切り抜き", "tab_pos": "位置",
        "rz_none": "使わない", "rz_scale": "倍率で", "rz_size": "サイズ指定",
        "sc_name": "倍率", "sc_size": "サイズ", "keep_ratio": "比率を保つ",
        "method": "方式", "m_nearest": "くっきり(ドット)", "m_smooth": "なめらか", "m_sharp": "シャープ",
        "pad_name": "残す余白",
        "crop_drag_hint": "◆ 左の元画像の上の枠をドラッグして範囲を選んでください (角=サイズ変更、内側=移動)",
        "crop_reset": "↻ 画像全体",
        "crop_hint": "切り抜きは背景を消した直後に、「透明な余白を切り取る」はその次に適用されます。",
        "cv_use": "キャンバス使用", "cv_fit": "サイズ合わせ",
        "off_x": "横に移動", "off_y": "縦に移動", "margin": "内側の余白",
        "size_info": "元 {ow}×{oh}px  ➜  結果 {w}×{h}px",
    },
    "zh": {
        "win_title": "AI 游戏资源编辑器",
        "title": "✦ AI 游戏资源编辑器 ✦",
        "subtitle": "从去除背景到调整大小、位置，一站搞定！",
        "settings": "⚙ 设置",
        "sec1": "添加图片", "sec2": "预览 · 调整", "sec3": "保存",
        "btn_images": "▣ 图片", "btn_folder": "▶ 文件夹", "btn_clear": "✖ 清空",
        "hint_dnd": "▼ 也可以把文件或文件夹拖到这里",
        "hint_nodnd": "请用按钮选择图片",
        "orig": "原图", "result": "结果 (方格 = 透明)", "placeholder": "请添加\n图片",
        "tol_name": "擦除强度", "tol_tip": "背景残留就调高，图像被削掉就调低",
        "fea_name": "边缘柔和度", "fea_tip": "0 = 清晰 (适合像素画)",
        "bg_color": "背景色", "auto_detect": "自动检测", "pick_color": "◆ 选择颜色", "auto": "↻ 自动",
        "trim": "裁掉透明边距", "glob": "同时擦除图内相同颜色",
        "save_to": "保存位置: {p}", "save_default": "原图旁边 ('transparent' 文件夹)",
        "change_save": "▶ 更改保存位置",
        "start": "✦  开始透明化！  ✦", "working": "✦  处理中…  ✦",
        "st_empty": "请添加图片！",
        "st_ready": "✔ 已准备好 {n} 张图片！请点击下方按钮",
        "st_work": "施展魔法中… {i}/{n}",
        "st_done": "★ 完成！成功 {ok} 张", "st_fail": "，失败 {f} 张",
        "st_preview_fail": "预览失败: {e}",
        "warn_title": "提示", "warn_empty": "请先添加图片！",
        "done_title": "完成", "done_msg": "已保存 {ok} 张！\n\n保存位置:\n{d}",
        "done_none": "没有保存任何文件。", "done_fails": "失败:", "open_q": "要打开保存文件夹吗？",
        "err_title": "失败",
        "dlg_images": "选择图片", "dlg_all": "所有文件", "dlg_img_type": "图片",
        "dlg_folder": "选择文件夹 (包含子文件夹)", "dlg_out": "选择保存文件夹",
        "dlg_color": "选择背景色",
        "set_title": "设置",
        "set_lang": "语言 / Language",
        "set_cache": "清理缓存",
        "set_cache_info": "临时文件大小: {s}\n(错误日志和临时文件，不会删除你的图片)",
        "set_cache_btn": "✖ 清理缓存",
        "set_cache_done": "已清理 {s}！",
        "set_save": "自动保存路径",
        "set_current": "当前路径:",
        "set_change": "▶ 更改", "set_reset": "↻ 恢复默认(原图旁边)", "set_open": "▣ 打开文件夹",
        "set_close": "关闭",
        "set_saved": "设置会自动保存",
        "tab_bg": "背景", "tab_size": "缩放/放大", "tab_crop": "裁剪", "tab_pos": "位置",
        "rz_none": "不使用", "rz_scale": "按倍率", "rz_size": "指定尺寸",
        "sc_name": "倍率", "sc_size": "尺寸", "keep_ratio": "保持比例",
        "method": "方式", "m_nearest": "清晰(像素)", "m_smooth": "平滑", "m_sharp": "锐化",
        "pad_name": "保留边距",
        "crop_drag_hint": "◆ 拖动左侧原图上的方框来选择裁剪范围 (角=改大小, 内部=移动)",
        "crop_reset": "↻ 完整图片",
        "crop_hint": "裁剪在去除背景后立即应用，「裁掉透明边距」在其之后应用。",
        "cv_use": "使用画布", "cv_fit": "适应画布",
        "off_x": "横向移动", "off_y": "纵向移动", "margin": "内边距",
        "size_info": "原图 {ow}×{oh}px  ➜  结果 {w}×{h}px",
    },
}


# ======================================================================
# 설정 저장/불러오기, 캐시, 오류 기록
# ======================================================================
def log_error(text):
    """창이 없는 exe에서도 원인을 알 수 있게 error_log.txt에 남긴다."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(text + chr(10))
    except Exception:
        pass


def load_settings():
    cfg = {"lang": "ko", "outdir": ""}
    try:
        cfg.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    if cfg["lang"] not in T:
        cfg["lang"] = "ko"
    return cfg


def save_settings(cfg):
    try:
        SETTINGS_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _size_of(p):
    if p.is_file():
        return p.stat().st_size
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return 0


def cache_size():
    total = 0
    for p in CACHE_ITEMS:
        try:
            total += _size_of(p)
        except OSError:
            pass
    return total


def clear_cache():
    for p in CACHE_ITEMS:
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        except OSError:
            pass


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ======================================================================
# 게임 스타일 위젯 (모든 크기는 sc()로 배율 적용)
# ======================================================================
class GameButton(tk.Canvas):
    """둥근 입체 버튼. width를 안 주면 글자 길이에 맞춘다."""

    def __init__(self, parent, text, command, color=GOLD, dark=GOLD_D, fg=DARK,
                 width=None, height=46, font=None):
        self.font = font or F(11)
        h = sc(height)
        w = sc(width) if width else tkfont.Font(font=self.font).measure(text) + sc(30)
        super().__init__(parent, width=w, height=h + sc(6), bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.text, self.command, self.color, self.dark, self.fg = text, command, color, dark, fg
        self.w, self.h = w, h
        self.state, self.hover, self.pressed = "normal", False, False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._draw()

    def _release(self, e):
        was = self.pressed
        self._set(pressed=False)
        if was and self.state == "normal" and 0 <= e.x <= self.w and 0 <= e.y <= self.h + sc(6):
            self.command()

    def config_state(self, state, text=None):
        self.state = state
        if text is not None:
            self.text = text
        self.config(cursor="hand2" if state == "normal" else "arrow")
        self._draw()

    def restyle(self, color, dark, fg):
        """탭·선택 버튼(칩)의 켜짐/꺼짐 색을 바꾼다."""
        self.color, self.dark, self.fg = color, dark, fg
        self._draw()

    def _draw(self):
        self.delete("all")
        r, sh, dn = sc(13), sc(6), sc(3)
        off = dn if self.pressed and self.state == "normal" else 0
        face = self.color if self.state == "normal" else "#6b6396"
        base = self.dark if self.state == "normal" else "#4b4478"
        if self.hover and self.state == "normal":
            face = shade(face, 1.08)
        round_rect(self, 1, sh, self.w - 1, self.h + sh - 1, r, fill=base)
        round_rect(self, 1, dn + off, self.w - 1, self.h + dn - 1 + off, r, fill=face)
        self.create_line(sc(14), sc(8) + off, self.w - sc(14), sc(8) + off,
                         fill=shade(face, 1.25) if self.state == "normal" else face,
                         width=max(1, sc(2)), capstyle="round")
        self.create_text(self.w / 2, self.h / 2 + dn + off, text=self.text,
                         fill=self.fg if self.state == "normal" else "#c9c3e8", font=self.font)


class GameSlider(tk.Canvas):
    def __init__(self, parent, var, lo, hi, color=GOLD, width=170, on_change=None, suffix=""):
        self.tw = sc(width)
        super().__init__(parent, width=self.tw + sc(66), height=sc(30), bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self.color, self.on_change = var, lo, hi, color, on_change
        self.suffix = suffix
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self._draw()

    def _drag(self, e):
        f = min(1, max(0, (e.x - sc(12)) / self.tw))
        self.var.set(round(self.lo + f * (self.hi - self.lo)))
        self._draw()
        if self.on_change:
            self.on_change()

    def _draw(self):
        self.delete("all")
        f = (self.var.get() - self.lo) / (self.hi - self.lo)
        x = sc(12) + f * self.tw
        round_rect(self, sc(8), sc(10), sc(16) + self.tw, sc(20), sc(5), fill=DARK)
        if x > sc(14):
            round_rect(self, sc(8), sc(10), x, sc(20), sc(5), fill=self.color)
        k = sc(11)
        self.create_oval(x - k, sc(4), x + k, sc(26), fill=shade(self.color, .75), outline="")
        self.create_oval(x - k, sc(2), x + k, sc(24), fill="#fff1b8" if self.color == GOLD else GOLD,
                         outline=TEXT, width=max(1, sc(2)))
        self.create_text(self.tw + sc(42), sc(15), text=f"{int(self.var.get())}{self.suffix}", fill=TEXT,
                         font=F(10))


class GameToggle(tk.Canvas):
    def __init__(self, parent, text, var, command=None):
        self.font = F(10, False)
        w = sc(62) + tkfont.Font(font=self.font).measure(text) + sc(10)
        super().__init__(parent, width=w, height=sc(32), bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.text, self.var, self.command = text, var, command
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, e):
        self.var.set(not self.var.get())
        self._draw()
        if self.command:
            self.command()

    def _draw(self):
        self.delete("all")
        on = self.var.get()
        round_rect(self, sc(2), sc(4), sc(50), sc(28), sc(12), fill=MINT if on else DARK, outline=PANEL_HI)
        x = sc(38) if on else sc(14)
        self.create_oval(x - sc(9), sc(7), x + sc(9), sc(25), fill=TEXT if on else SUB, outline="")
        self.create_text(sc(60), sc(16), text=self.text, anchor="w", fill=TEXT, font=self.font)


class GameBar(tk.Canvas):
    def __init__(self, parent, value=0):
        super().__init__(parent, height=sc(20), bg=parent["bg"], highlightthickness=0)
        self.value = value
        self.bind("<Configure>", lambda e: self.set(self.value))

    def set(self, pct):
        self.value = pct
        self.delete("all")
        w, h = self.winfo_width(), sc(20)
        round_rect(self, 0, 0, w, h, sc(9), fill=DARK, outline=PANEL_HI)
        if pct > 0:
            round_rect(self, 2, 2, max(sc(20), 2 + (w - 4) * pct / 100), h - 2, sc(8), fill=MINT)


class GameAlignGrid(tk.Canvas):
    """3x3 위치 선택 격자. (왼쪽·가운데·오른쪽) x (위·가운데·아래)"""

    def __init__(self, parent, var_x, var_y, on_change=None):
        self.cell = sc(26)
        super().__init__(parent, width=self.cell * 3 + sc(8), height=self.cell * 3 + sc(8), bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.vx, self.vy, self.on_change = var_x, var_y, on_change
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, e):
        cx = min(2, max(0, (e.x - sc(4)) // self.cell))
        cy = min(2, max(0, (e.y - sc(4)) // self.cell))
        self.vx.set(int(cx))
        self.vy.set(int(cy))
        self._draw()
        if self.on_change:
            self.on_change()

    def _draw(self):
        self.delete("all")
        c, g = self.cell, sc(3)
        for j in range(3):
            for i in range(3):
                on = (i, j) == (self.vx.get(), self.vy.get())
                x, y = sc(4) + i * c, sc(4) + j * c
                round_rect(self, x + g, y + g, x + c - g, y + c - g, sc(5),
                           fill=GOLD if on else DARK, outline=TEXT if on else PANEL_HI)
                if on:
                    self.create_oval(x + c / 2 - sc(3), y + c / 2 - sc(3), x + c / 2 + sc(3), y + c / 2 + sc(3),
                                     fill=DARK, outline="")


def game_entry(parent, var, width=5):
    """게임 스타일 숫자 입력칸."""
    return tk.Entry(parent, textvariable=var, width=width, justify="center", bg=DARK, fg=TEXT,
                    insertbackground=GOLD, relief="flat", bd=sc(4), font=F(10, False),
                    highlightthickness=max(1, sc(2)), highlightbackground=PANEL_HI, highlightcolor=GOLD,
                    selectbackground=GOLD, selectforeground=DARK)


class CropBox:
    """원본 미리보기 위에 그리는 대화형 자르기 상자 (모바일 사진 자르기 스타일).

    모서리 4개·변 중앙 4개 손잡이를 끌어 크기를 바꾸고, 상자 안을 끌면 통째로 옮긴다.
    바깥쪽은 어둡게 표시된다. 실제 상태는 여전히 app.crop_v(좌·상·우·하 %) 4개에 저장되므로
    엔진(postprocess)은 그대로 쓴다 — 이 클래스는 그 값을 그림 위에서 조작하는 입력 장치일 뿐이다.
    """
    MIN_FRAC = 0.08   # 상자가 이보다 작아지지 않도록 (원본 대비 최소 8%)

    def __init__(self, app):
        self.app = app
        self.canvas = app.cv_before
        self.img_size = None    # (표시된 이미지 픽셀 너비, 높이) — 없으면(placeholder) 아무것도 안 그림
        self.active = False     # '자르기' 탭일 때만 손잡이 표시
        self.drag = None        # None 또는 'move'/'tl'/'tr'/'bl'/'br'/'t'/'b'/'l'/'r'
        self.anchor = None      # 드래그 시작 시점의 상자(px)와 마우스 좌표
        for seq, cb in (("<ButtonPress-1>", self._press), ("<B1-Motion>", self._motion),
                       ("<ButtonRelease-1>", self._release), ("<Motion>", self._hover),
                       ("<Leave>", lambda e: self.canvas.config(cursor=""))):
            self.canvas.bind(seq, cb, add=True)

    def set_active(self, on):
        self.active = on
        self.draw()

    def set_image_box(self, pw, ph):
        self.img_size = (pw, ph)
        self.draw()

    def _img_box(self):
        cw, ch = int(self.canvas["width"]), int(self.canvas["height"])
        pw, ph = self.img_size
        cx, cy = cw // 2, ch // 2
        return (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2)

    def _rect(self):
        """crop_v(%) -> 캔버스 픽셀 좌표의 상자."""
        x0, y0, x1, y1 = self._img_box()
        w, h = x1 - x0, y1 - y0
        l, t, r, b = (v.get() for v in self.app.crop_v)
        return (x0 + w * l / 100, y0 + h * t / 100, x1 - w * r / 100, y1 - h * b / 100)

    def _handles(self, rect):
        x0, y0, x1, y1 = rect
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1),
                "t": (mx, y0), "b": (mx, y1), "l": (x0, my), "r": (x1, my)}

    CURSORS = {"tl": "size_nw_se", "br": "size_nw_se", "tr": "size_ne_sw", "bl": "size_ne_sw",
              "t": "size_ns", "b": "size_ns", "l": "size_we", "r": "size_we", "move": "fleur"}

    def _hit(self, x, y):
        if not (self.active and self.img_size):
            return None
        rect = self._rect()
        tol = sc(9)
        for name, (hx, hy) in self._handles(rect).items():
            if abs(x - hx) <= tol and abs(y - hy) <= tol:
                return name
        x0, y0, x1, y1 = rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            return "move"
        return None

    def _hover(self, e):
        if self.drag is None:
            hit = self._hit(e.x, e.y)
            self.canvas.config(cursor=self.CURSORS.get(hit, ""))

    def _press(self, e):
        hit = self._hit(e.x, e.y)
        if not hit:
            return
        self.drag = hit
        self.anchor = (self._rect(), e.x, e.y)

    def _motion(self, e):
        if not self.drag:
            return
        (rx0, ry0, rx1, ry1), sx, sy = self.anchor
        dx, dy = e.x - sx, e.y - sy
        x0, y0, x1, y1 = self._img_box()
        w, h = x1 - x0, y1 - y0
        minw, minh = w * self.MIN_FRAC, h * self.MIN_FRAC
        nx0, ny0, nx1, ny1 = rx0, ry0, rx1, ry1
        if self.drag == "move":
            dx = max(x0 - rx0, min(dx, x1 - rx1))
            dy = max(y0 - ry0, min(dy, y1 - ry1))
            nx0, nx1 = rx0 + dx, rx1 + dx
            ny0, ny1 = ry0 + dy, ry1 + dy
        else:
            if "l" in self.drag:
                nx0 = max(x0, min(rx0 + dx, rx1 - minw))
            if "r" in self.drag:
                nx1 = min(x1, max(rx1 + dx, rx0 + minw))
            if "t" in self.drag:
                ny0 = max(y0, min(ry0 + dy, ry1 - minh))
            if "b" in self.drag:
                ny1 = min(y1, max(ry1 + dy, ry0 + minh))
        l, t = (nx0 - x0) / w * 100, (ny0 - y0) / h * 100
        r, b = (x1 - nx1) / w * 100, (y1 - ny1) / h * 100
        for var, val in zip(self.app.crop_v, (l, t, r, b)):
            var.set(max(0, min(100, val)))
        self.draw()
        self.app._schedule()

    def _release(self, e):
        self.drag = None
        self.anchor = None
        self._hover(e)

    def reset(self):
        for var in self.app.crop_v:
            var.set(0)
        self.draw()
        self.app._schedule()

    def draw(self):
        self.canvas.delete("cropui")
        if not (self.active and self.img_size):
            return
        x0, y0, x1, y1 = self._img_box()
        rx0, ry0, rx1, ry1 = self._rect()
        cw, ch = int(self.canvas["width"]), int(self.canvas["height"])
        # 바깥쪽을 어둡게 (stipple = 반투명 느낌을 흉내)
        for bx0, by0, bx1, by1 in ((0, 0, cw, ry0), (0, ry1, cw, ch),
                                   (0, ry0, rx0, ry1), (rx1, ry0, cw, ry1)):
            if bx1 > bx0 and by1 > by0:
                self.canvas.create_rectangle(bx0, by0, bx1, by1, fill=DARK, outline="",
                                             stipple="gray50", tags="cropui")
        if self.drag:  # 드래그 중에는 3분할 안내선
            for i in (1, 2):
                gx = rx0 + (rx1 - rx0) * i / 3
                gy = ry0 + (ry1 - ry0) * i / 3
                self.canvas.create_line(gx, ry0, gx, ry1, fill=TEXT, stipple="gray25", tags="cropui")
                self.canvas.create_line(rx0, gy, rx1, gy, fill=TEXT, stipple="gray25", tags="cropui")
        self.canvas.create_rectangle(rx0, ry0, rx1, ry1, outline=GOLD, width=max(1, sc(2)), tags="cropui")
        hs = sc(5)
        for hx, hy in self._handles((rx0, ry0, rx1, ry1)).values():
            self.canvas.create_rectangle(hx - hs, hy - hs, hx + hs, hy + hs, fill=GOLD, outline=DARK,
                                         width=max(1, sc(1)), tags="cropui")


class Card(tk.Frame):
    """제목 뱃지가 달린 카드."""

    def __init__(self, parent, num, title, color):
        super().__init__(parent, bg=PANEL, highlightbackground=PANEL_HI, highlightthickness=max(1, sc(2)))
        head = tk.Frame(self, bg=PANEL)
        head.pack(fill="x", padx=sc(12), pady=(sc(10), sc(4)))
        if num is not None:
            d = sc(30)
            badge = tk.Canvas(head, width=d, height=d, bg=PANEL, highlightthickness=0)
            badge.create_oval(1, 1, d - 1, d - 1, fill=color, outline=TEXT, width=max(1, sc(2)))
            badge.create_text(d / 2, d / 2, text=str(num), fill=DARK, font=F(11))
            badge.pack(side="left")
        tk.Label(head, text=title, bg=PANEL, fg=GOLD, font=F(13)).pack(side="left", padx=sc(8))
        self.body = tk.Frame(self, bg=PANEL)
        self.body.pack(fill="both", expand=True, padx=sc(12), pady=(sc(2), sc(12)))


def fixed_label(parent, text, width_px, font, fg=TEXT):
    """일정한 너비를 차지하는 왼쪽 정렬 라벨 (언어가 바뀌어도 줄이 어긋나지 않게)."""
    fr = tk.Frame(parent, bg=parent["bg"], width=sc(width_px))
    fr.pack_propagate(False)
    lb = tk.Label(fr, text=text, bg=parent["bg"], fg=fg, font=font, anchor="w", justify="left",
                  wraplength=sc(width_px))
    lb.pack(fill="both", expand=True)
    return fr


# ======================================================================
# 메인 창
# ======================================================================
class App(Root):
    BASE_W = 1012
    BASE_H = 571

    def __init__(self):
        super().__init__()
        self.configure(bg=BG)
        self.cfg = load_settings()
        self.files = []
        self.sel = 0
        self.tol = tk.DoubleVar(value=30)
        self.fea = tk.DoubleVar(value=20)
        self.trim = tk.BooleanVar(value=False)
        self.glob = tk.BooleanVar(value=False)
        # 크기 · 자르기 · 위치 옵션 (배경 제거 뒤에 순서대로 적용: 자르기 -> 여백 -> 크기 -> 캔버스/위치)
        self.tab = 0
        self.pad = tk.DoubleVar(value=0)
        self.crop_v = [tk.DoubleVar(value=0) for _ in range(4)]      # 왼쪽, 위, 오른쪽, 아래 (%)
        self.rz_mode = tk.StringVar(value="none")                    # none | scale | size
        self.scale = tk.DoubleVar(value=200)
        self.rz_w, self.rz_h = tk.StringVar(value="512"), tk.StringVar(value="512")
        self.keep_ratio = tk.BooleanVar(value=True)
        self.method = tk.StringVar(value="smooth")                   # nearest | smooth | sharp
        self.cv_on = tk.BooleanVar(value=False)
        self.cv_w, self.cv_h = tk.StringVar(value="256"), tk.StringVar(value="256")
        self.fit = tk.BooleanVar(value=False)
        self.ax, self.ay = tk.IntVar(value=1), tk.IntVar(value=1)
        self.off_x, self.off_y = tk.DoubleVar(value=0), tk.DoubleVar(value=0)
        self.margin = tk.DoubleVar(value=0)
        for v in (self.rz_w, self.rz_h, self.cv_w, self.cv_h, self.rz_mode, self.method):
            v.trace_add("write", lambda *a: self._schedule())        # 입력하면 미리보기 갱신
        self.bgcolor = None
        self._info_text = ""
        self._job = None
        self._rb_job = None
        self._ready = False
        self.busy = False
        self.bar_value = 0
        self._status = ("st_empty", {}, SUB)
        self._status_extra = ""
        self.settings_win = None
        self.q = queue.Queue()
        if DND_FILES:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.on_drop)
        self._build()
        self.update_idletasks()
        App.BASE_W, App.BASE_H = self.winfo_reqwidth() + 4, self.winfo_reqheight() + 4
        self.geometry(f"{App.BASE_W}x{App.BASE_H}")
        self.minsize(int(App.BASE_W * 0.6), int(App.BASE_H * 0.6))
        self.bind("<Configure>", self._on_configure)
        self.after(500, lambda: setattr(self, "_ready", True))
        try:  # 창 아이콘
            self._icon = ImageTk.PhotoImage(Image.open(ASSET_DIR / "icon.png"))
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        paths = [a for a in sys.argv[1:] if not a.startswith("--")]  # exe 아이콘 위로 파일을 끌어다 놓은 경우
        if paths:
            self.after(300, lambda: self.add(paths))

    def report_callback_exception(self, exc, val, tb):
        log_error("".join(traceback.format_exception(exc, val, tb)))

    def tr(self, key, **kw):
        s = T[self.cfg["lang"]].get(key) or T["ko"][key]
        return s.format(**kw) if kw else s

    # ------------------------------------------------------------ 배율 (창 크기 연동)
    def _on_configure(self, e):
        if e.widget is not self or not self._ready:
            return
        if self._rb_job:
            self.after_cancel(self._rb_job)
        self._rb_job = self.after(250, self._maybe_rebuild)

    def _maybe_rebuild(self):
        global S
        self._rb_job = None
        s = min(self.winfo_width() / App.BASE_W, self.winfo_height() / App.BASE_H)
        s = round(max(0.6, min(3.0, s)) * 20) / 20  # 0.05 단위
        if abs(s - S) >= 0.05:
            S = s
            self.rebuild()

    def rebuild(self):
        """현재 배율/언어로 화면을 다시 그린다 (상태는 유지)."""
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self._build()
        self._restore()

    # ------------------------------------------------------------ UI
    def _build(self):
        self.title(self.tr("win_title"))
        title = tk.Canvas(self, height=sc(68), bg=BG, highlightthickness=0)
        title.pack(fill="x")
        txt = self.tr("title")
        t1 = title.create_text(500, sc(26), text=txt, fill=GOLD, font=F(26))
        t2 = title.create_text(500 + sc(2), sc(28), text=txt, fill=GOLD_D, font=F(26))
        title.tag_lower(t2)
        t3 = title.create_text(500, sc(55), text=self.tr("subtitle"), fill=SUB, font=F(9, False))
        title.bind("<Configure>", lambda e: (title.coords(t1, e.width / 2, sc(26)),
                                             title.coords(t2, e.width / 2 + sc(2), sc(28)),
                                             title.coords(t3, e.width / 2, sc(55))))
        GameButton(title, self.tr("settings"), self.open_settings, INACTIVE, INACTIVE_D, TEXT,
                   height=34, font=F(10)).place(relx=1.0, x=-sc(14), y=sc(8), anchor="ne")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=sc(14))
        left = tk.Frame(main, bg=BG, width=sc(LEFT_W))
        left.pack(side="left", fill="y", padx=(0, sc(10)))
        left.pack_propagate(False)
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # 1. 이미지 담기
        c1 = Card(left, 1, self.tr("sec1"), SKY)
        c1.pack(fill="both", expand=True, pady=(0, sc(8)))
        row = tk.Frame(c1.body, bg=PANEL)
        row.pack(fill="x")
        f10 = F(10)
        GameButton(row, self.tr("btn_images"), self.pick_files, SKY, SKY_D, DARK, height=38, font=f10).pack(side="left")
        GameButton(row, self.tr("btn_folder"), self.pick_folder, MINT, MINT_D, DARK, height=38, font=f10).pack(
            side="left", padx=sc(5))
        GameButton(row, self.tr("btn_clear"), self.clear, PINK, PINK_D, TEXT, height=38, font=f10).pack(side="left")
        lf = tk.Frame(c1.body, bg=DARK, highlightbackground=PANEL_HI, highlightthickness=max(1, sc(2)))
        lf.pack(fill="both", expand=True, pady=(sc(6), sc(2)))
        self.listbox = tk.Listbox(lf, height=4, selectmode="browse", bg=DARK, fg=TEXT, font=F(9, False),
                                  selectbackground=GOLD, selectforeground=DARK, relief="flat", bd=sc(6),
                                  highlightthickness=0, activestyle="none", exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        tk.Label(c1.body, bg=PANEL, fg=SUB, font=F(9, False), justify="left", anchor="w",
                 wraplength=sc(LEFT_W - 50),
                 text=self.tr("hint_dnd") if DND_FILES else self.tr("hint_nodnd")).pack(anchor="w")
        if DND_FILES:
            for w in (self.listbox, c1):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)

        # 3. 저장
        c3 = Card(left, 3, self.tr("sec3"), PINK)
        c3.pack(fill="x")
        self.out_lbl = tk.Label(c3.body, text="", bg=PANEL, fg=SUB, font=F(9, False), anchor="w",
                                justify="left", wraplength=sc(LEFT_W - 50))
        self.out_lbl.pack(fill="x")
        GameButton(c3.body, self.tr("change_save"), self.pick_out, SKY, SKY_D, DARK, height=34, font=f10).pack(
            anchor="w", pady=(sc(4), 0))
        self._refresh_out_label()

        # 2. 미리보기 · 조절
        c2 = Card(right, 2, self.tr("sec2"), GOLD)
        c2.pack(fill="both", expand=True)
        pv = tk.Frame(c2.body, bg=PANEL)
        pv.pack()
        self.cv_before = self._preview_box(pv, self.tr("orig"), SUB)
        self.cropbox = CropBox(self)
        tk.Label(pv, text="➜", bg=PANEL, fg=GOLD, font=F(22)).pack(side="left", padx=sc(6))
        self.cv_after = self._preview_box(pv, self.tr("result"), MINT)
        self.info_lbl = tk.Label(c2.body, text=self._info_text, bg=PANEL, fg=GOLD, font=F(9, False))
        self.info_lbl.pack(pady=(sc(2), 0))
        self.chips = []

        # 탭: 배경 / 크기 · 업스케일 / 자르기 / 위치
        tabbar = tk.Frame(c2.body, bg=PANEL)
        tabbar.pack(fill="x", pady=(sc(4), sc(2)))
        self.tab_btns = []
        for i, key in enumerate(("tab_bg", "tab_size", "tab_crop", "tab_pos")):
            b = GameButton(tabbar, self.tr(key), lambda i=i: self._select_tab(i), INACTIVE, INACTIVE_D, TEXT,
                           height=28, font=f10)
            b.pack(side="left", padx=(0, sc(5)))
            self.tab_btns.append(b)
        tabbody = tk.Frame(c2.body, bg=PANEL, height=sc(TAB_H))
        tabbody.pack(fill="x")
        tabbody.pack_propagate(False)
        self.tab_frames = []
        for builder in (self._tab_bg, self._tab_size, self._tab_crop, self._tab_pos):
            fr = tk.Frame(tabbody, bg=PANEL)
            builder(fr)
            self.tab_frames.append(fr)
        self._select_tab(self.tab)

        # 시작 (아래)
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=sc(14), pady=(sc(8), sc(10)))
        self.run_btn = GameButton(bottom, self.tr("working") if self.busy else self.tr("start"), self.run,
                                  GOLD, GOLD_D, DARK, width=LEFT_W, height=52, font=F(16))
        self.run_btn.pack(side="left", padx=(0, sc(10)))
        if self.busy:
            self.run_btn.config_state("disabled")
        info = tk.Frame(bottom, bg=BG)
        info.pack(side="left", fill="x", expand=True)
        self.bar = GameBar(info, self.bar_value)
        self.bar.pack(fill="x", pady=(sc(8), sc(6)))
        self.status = tk.Label(info, text="", bg=BG, fg=SUB, font=F(10), anchor="w")
        self.status.pack(fill="x")
        self._render_status()

    # ------------------------------------------------------------ 탭 (배경 / 크기 / 자르기 / 위치)
    def _select_tab(self, i):
        self.tab = i
        for fr in self.tab_frames:
            fr.pack_forget()
        self.tab_frames[i].pack(fill="both", expand=True)
        for j, b in enumerate(self.tab_btns):
            b.restyle(*((GOLD, GOLD_D, DARK) if j == i else (INACTIVE, INACTIVE_D, TEXT)))
        self.cropbox.set_active(i == 2)  # 2 = 자르기 탭

    def _chips(self, parent, options, var):
        """여러 개 중 하나를 고르는 버튼 묶음."""
        for key, label in options:
            b = GameButton(parent, label, lambda k=key: self._chip_click(var, k), INACTIVE, INACTIVE_D, TEXT,
                           height=26, font=F(10))
            b.pack(side="left", padx=(0, sc(5)))
            self.chips.append((var, key, b))
        self._refresh_chips()

    def _chip_click(self, var, key):
        var.set(key)
        self._refresh_chips()

    def _refresh_chips(self):
        for var, key, b in self.chips:
            b.restyle(*((GOLD, GOLD_D, DARK) if var.get() == key else (INACTIVE, INACTIVE_D, TEXT)))

    def _mini(self, parent, label, var, lo, hi, color, width=110, label_w=48, suffix=""):
        """이름 + 슬라이더 한 줄 (가로로 나란히 놓을 수 있게 pack(side=left))."""
        r = tk.Frame(parent, bg=PANEL)
        fixed_label(r, label, label_w, F(10)).pack(side="left", fill="y")
        GameSlider(r, var, lo, hi, color, width, self._schedule, suffix).pack(side="left")
        return r

    def _num(self, var, default=0):
        try:
            return max(0, min(MAX_PX, int(float(var.get()))))
        except (ValueError, tk.TclError):
            return default

    def opts(self):
        """현재 화면의 크기·자르기·위치 옵션 (remove_bg.postprocess 에 그대로 전달)."""
        cw, ch = self._num(self.cv_w), self._num(self.cv_h)
        o = rb.default_opts()
        o.update(
            crop=tuple(v.get() for v in self.crop_v), trim=self.trim.get(), pad=int(self.pad.get()),
            resize=self.rz_mode.get(), scale=self.scale.get(),
            size=(self._num(self.rz_w), self._num(self.rz_h)), keep_ratio=self.keep_ratio.get(),
            method=self.method.get(),
            canvas=(cw, ch) if self.cv_on.get() and cw > 0 and ch > 0 else None,
            fit=self.fit.get(), align=(self.ax.get(), self.ay.get()),
            offset=(self.off_x.get(), self.off_y.get()), margin=int(self.margin.get()))
        return o

    def _tab_bg(self, fr):
        f10 = F(10)
        self._slider_row(fr, self.tr("tol_name"), self.tol, 0, 120, GOLD, self.tr("tol_tip"))
        self._slider_row(fr, self.tr("fea_name"), self.fea, 0, 60, PINK, self.tr("fea_tip"))
        rowc = tk.Frame(fr, bg=PANEL)
        rowc.pack(fill="x", pady=(sc(4), 0))
        fixed_label(rowc, self.tr("bg_color"), 90, f10).pack(side="left", fill="y")
        self.swatch = tk.Canvas(rowc, width=sc(28), height=sc(28), bg=PANEL, highlightthickness=0)
        self.swatch.pack(side="left")
        self.bg_text = tk.Label(rowc, text=self._bg_text(), bg=PANEL, fg=SUB, font=F(10, False), anchor="w")
        self.bg_text.pack(side="left", padx=sc(6))
        GameButton(rowc, self.tr("pick_color"), self.pick_color, SKY, SKY_D, DARK, height=32, font=f10).pack(side="left")
        GameButton(rowc, self.tr("auto"), self.auto_color, GOLD, GOLD_D, DARK, height=32, font=f10).pack(
            side="left", padx=sc(6))
        self._paint_swatch()
        tg = tk.Frame(fr, bg=PANEL)
        tg.pack(fill="x", pady=(sc(2), 0))
        GameToggle(tg, self.tr("glob"), self.glob, self.update_preview).pack(side="left")

    def _tab_size(self, fr):
        r1 = tk.Frame(fr, bg=PANEL)
        r1.pack(fill="x", pady=(0, sc(2)))
        self._chips(r1, [("none", self.tr("rz_none")), ("scale", self.tr("rz_scale")),
                         ("size", self.tr("rz_size"))], self.rz_mode)
        r2 = tk.Frame(fr, bg=PANEL)
        r2.pack(fill="x")
        fixed_label(r2, self.tr("sc_name"), 64, F(10)).pack(side="left", fill="y")
        self.scale_slider = GameSlider(r2, self.scale, 10, 400, GOLD, 170, self._on_scale, "%")
        self.scale_slider.pack(side="left")
        for label, val in (("½", 50), ("×1", 100), ("×2", 200), ("×3", 300), ("×4", 400)):
            GameButton(r2, label, lambda v=val: self._set_scale(v), SKY, SKY_D, DARK, width=38, height=22,
                       font=F(9)).pack(side="left", padx=(0, sc(3)))
        r3 = tk.Frame(fr, bg=PANEL)
        r3.pack(fill="x", pady=(sc(2), 0))
        fixed_label(r3, self.tr("sc_size"), 64, F(10)).pack(side="left", fill="y")
        for var, sep in ((self.rz_w, "×"), (self.rz_h, "")):
            e = game_entry(r3, var, 6)
            e.pack(side="left", padx=(0, sc(4)))
            e.bind("<KeyRelease>", lambda ev: self._auto_mode("size"))
            if sep:
                tk.Label(r3, text=sep, bg=PANEL, fg=SUB, font=F(10)).pack(side="left", padx=(0, sc(4)))
        tk.Label(r3, text="px", bg=PANEL, fg=SUB, font=F(9, False)).pack(side="left", padx=(0, sc(8)))
        GameToggle(r3, self.tr("keep_ratio"), self.keep_ratio, self._schedule).pack(side="left")
        r4 = tk.Frame(fr, bg=PANEL)
        r4.pack(fill="x", pady=(sc(4), 0))
        fixed_label(r4, self.tr("method"), 64, F(10)).pack(side="left", fill="y")
        self._chips(r4, [("nearest", self.tr("m_nearest")), ("smooth", self.tr("m_smooth")),
                         ("sharp", self.tr("m_sharp"))], self.method)

    def _tab_crop(self, fr):
        tk.Label(fr, text=self.tr("crop_drag_hint"), bg=PANEL, fg=TEXT, font=F(10, False), anchor="w",
                 justify="left", wraplength=sc(560)).pack(fill="x", anchor="w")
        GameButton(fr, self.tr("crop_reset"), self.cropbox.reset, SKY, SKY_D, DARK, height=28,
                  font=F(10)).pack(anchor="w", pady=(sc(4), sc(6)))
        r1 = tk.Frame(fr, bg=PANEL)
        r1.pack(fill="x")
        GameToggle(r1, self.tr("trim"), self.trim, self._schedule).pack(side="left")
        self._mini(r1, self.tr("pad_name"), self.pad, 0, 64, MINT, 110, 84, "px").pack(side="left", padx=(sc(8), 0))
        tk.Label(fr, text=self.tr("crop_hint"), bg=PANEL, fg=SUB, font=F(9, False), anchor="w",
                 justify="left", wraplength=sc(560)).pack(fill="x", pady=(sc(4), 0))

    def _tab_pos(self, fr):
        r1 = tk.Frame(fr, bg=PANEL)
        r1.pack(fill="x")
        cv_toggle = GameToggle(r1, self.tr("cv_use"), self.cv_on, self._schedule)
        cv_toggle.pack(side="left")
        for var, sep in ((self.cv_w, "×"), (self.cv_h, "")):
            e = game_entry(r1, var, 6)
            e.pack(side="left", padx=(0, sc(4)))
            e.bind("<KeyRelease>", lambda ev, t=cv_toggle: (self.cv_on.set(True), t._draw()))  # 입력하면 자동으로 켬
            if sep:
                tk.Label(r1, text=sep, bg=PANEL, fg=SUB, font=F(10)).pack(side="left", padx=(0, sc(4)))
        tk.Label(r1, text="px", bg=PANEL, fg=SUB, font=F(9, False)).pack(side="left", padx=(0, sc(8)))
        GameToggle(r1, self.tr("cv_fit"), self.fit, self._schedule).pack(side="left")
        r2 = tk.Frame(fr, bg=PANEL)
        r2.pack(fill="x", pady=(sc(4), 0))
        GameAlignGrid(r2, self.ax, self.ay, self._schedule).pack(side="left", padx=(sc(4), sc(12)))
        col = tk.Frame(r2, bg=PANEL)
        col.pack(side="left", fill="x", expand=True)
        for name, var, lo, hi, color in ((self.tr("off_x"), self.off_x, -200, 200, GOLD),
                                         (self.tr("off_y"), self.off_y, -200, 200, GOLD),
                                         (self.tr("margin"), self.margin, 0, 64, MINT)):
            self._mini(col, name, var, lo, hi, color, 170, 100, "px").pack(anchor="w")

    def _on_scale(self):
        self._auto_mode("scale")
        self._schedule()

    def _set_scale(self, v):
        self.scale.set(v)
        self.scale_slider._draw()
        self._auto_mode("scale")
        self._schedule()

    def _auto_mode(self, mode):
        if self.rz_mode.get() != mode:
            self.rz_mode.set(mode)
        self._refresh_chips()

    def _restore(self):
        for f in self.files:
            self.listbox.insert("end", self._list_text(f))
        if self.files:
            self.listbox.selection_set(min(self.sel, len(self.files) - 1))
            self.update_preview()

    def _preview_box(self, parent, caption, color):
        box = tk.Frame(parent, bg=PANEL)
        box.pack(side="left")
        tk.Label(box, text=caption, bg=PANEL, fg=color, font=F(9)).pack()
        cv = tk.Canvas(box, width=sc(PV_W), height=sc(PV_H), bg=DARK, highlightbackground=GOLD,
                       highlightthickness=max(1, sc(2)))
        cv.pack()
        cv.create_text(sc(PV_W) / 2, sc(PV_H) / 2, text=self.tr("placeholder"), fill=SUB, font=F(11),
                       justify="center", tags="ph")
        return cv

    def _slider_row(self, parent, name, var, lo, hi, color, tip):
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill="x", pady=sc(1))
        fixed_label(r, name, 128, F(10)).pack(side="left", fill="y")
        GameSlider(r, var, lo, hi, color, 170, self._schedule).pack(side="left")
        tk.Label(r, text=tip, bg=PANEL, fg=SUB, font=F(9, False), anchor="w", justify="left",
                 wraplength=sc(190)).pack(side="left", padx=sc(6))

    def _bg_text(self):
        if self.bgcolor is None:
            return self.tr("auto_detect")
        return "#%02x%02x%02x" % tuple(int(v) for v in self.bgcolor)

    def _paint_swatch(self):
        self.swatch.delete("all")
        d = sc(28)
        if self.bgcolor is None:
            round_rect(self.swatch, 2, 2, d - 2, d - 2, sc(8), fill=DARK, outline=PANEL_HI)
            self.swatch.create_text(d / 2, d / 2, text="A", fill=GOLD, font=F(11))
        else:
            round_rect(self.swatch, 2, 2, d - 2, d - 2, sc(8), fill=self._bg_text(), outline=TEXT)

    # ------------------------------------------------------------ 상태 문구
    def set_status(self, key, color, extra="", **kw):
        self._status = (key, kw, color)
        self._status_extra = extra
        self._render_status()

    def _render_status(self):
        key, kw, color = self._status
        self.status.config(text=self.tr(key, **kw) + self._status_extra, fg=color)

    def _refresh_out_label(self):
        p = self.cfg["outdir"] or self.tr("save_default")
        self.out_lbl.config(text=self.tr("save_to", p=p))

    # ------------------------------------------------------------ 파일
    def _list_text(self, f):
        return f"  {f.name}    ({f.parent.name})"

    def add(self, paths):
        for f in rb.collect(paths, True):
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", self._list_text(f))
        if self.files and not self.listbox.curselection():
            self.listbox.selection_set(0)
            self.sel = 0
        self.update_preview()
        self.set_status("st_ready", MINT, n=len(self.files))

    def on_drop(self, e):
        self.add(self.tk.splitlist(e.data))

    def _on_select(self, e=None):
        s = self.listbox.curselection()
        if s:
            self.sel = s[0]
        self.update_preview()

    def pick_files(self):
        p = filedialog.askopenfilenames(title=self.tr("dlg_images"), filetypes=[
            (self.tr("dlg_img_type"), "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.tif *.tiff *.gif"),
            (self.tr("dlg_all"), "*.*")])
        if p:
            self.add(p)

    def pick_folder(self):
        p = filedialog.askdirectory(title=self.tr("dlg_folder"))
        if p:
            self.add([p])

    def clear(self):
        self.files.clear()
        self.sel = 0
        self.listbox.delete(0, "end")
        for cv in (self.cv_before, self.cv_after):
            cv.delete("img")
            cv.itemconfig("ph", state="normal")
        self.cropbox.img_size = None
        self.cropbox.draw()
        self._info_text = ""
        self.info_lbl.config(text="")
        self.set_status("st_empty", SUB)

    def pick_out(self):
        p = filedialog.askdirectory(title=self.tr("dlg_out"))
        if p:
            self.cfg["outdir"] = p
            save_settings(self.cfg)
            self._refresh_out_label()

    def pick_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(title=self.tr("dlg_color"))
        if c and c[0]:
            self.bgcolor = rb.parse_color(",".join(str(int(v)) for v in c[0]))
            self.bg_text.config(text=self._bg_text())
            self._paint_swatch()
            self.update_preview()

    def auto_color(self):
        self.bgcolor = None
        self.bg_text.config(text=self._bg_text())
        self._paint_swatch()
        self.update_preview()

    # ------------------------------------------------------------ 미리보기
    def _schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(150, self.update_preview)

    def _show(self, cv, pil, attr):
        photo = ImageTk.PhotoImage(pil.convert("RGB"))
        setattr(self, attr, photo)
        cv.delete("img")
        cv.itemconfig("ph", state="hidden")
        cv.create_image(int(cv["width"]) // 2, int(cv["height"]) // 2, image=photo, tags="img")

    def update_preview(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self.files):
            return
        try:
            img = Image.open(self.files[sel[0]])
            img.load()
            ow, oh = img.size
            work = img.copy()
            work.thumbnail((PREVIEW_WORK, PREVIEW_WORK))
            ref = work.width / ow          # px 옵션(여백·크기·이동)을 축소 미리보기에 맞추는 비율
            res = rb.remove_bg(work, self.tol.get(), self.fea.get(), self.bgcolor, self.glob.get())
            res = rb.postprocess(res, self.opts(), ref)
            bw, bh = sc(PV_W) - 6, sc(PV_H) - 6
            before = self._fit_rgba(work.convert("RGBA"), bw, bh)
            after = self._fit_rgba(res, bw, bh)
            bg = checker(after.size, sc(10)).convert("RGBA")
            bg.alpha_composite(after)
            self._show(self.cv_before, before, "_pb")
            self._show(self.cv_after, bg, "_pa")
            self.cropbox.set_image_box(self._pb.width(), self._pb.height())
            self._info_text = self.tr("size_info", ow=ow, oh=oh, w=max(1, round(res.width / ref)),
                                      h=max(1, round(res.height / ref)))
            self.info_lbl.config(text=self._info_text)
        except Exception as e:
            self.set_status("st_preview_fail", PINK, e=e)

    @staticmethod
    def _fit_rgba(img, bw, bh):
        """칸에 맞게 표시용으로 키우거나 줄인다. 작은 도트 이미지는 정수배로 또렷하게 확대."""
        z = min(bw / img.width, bh / img.height)
        if z >= 2:
            k = int(z)
            return img.resize((img.width * k, img.height * k), Image.NEAREST)
        if z < 1:
            size = (max(1, int(img.width * z)), max(1, int(img.height * z)))
            return img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
        return img

    # ------------------------------------------------------------ 실행
    def run(self):
        if not self.files:
            messagebox.showwarning(self.tr("warn_title"), self.tr("warn_empty"))
            return
        self.busy = True
        self.run_btn.config_state("disabled", self.tr("working"))
        args = (self.tol.get(), self.fea.get(), self.bgcolor, self.glob.get(), self.opts(),
                self.cfg["outdir"], list(self.files))
        threading.Thread(target=self._work, args=args, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        while True:
            try:
                kind, *v = self.q.get_nowait()
            except queue.Empty:
                self.after(100, self._poll)
                return
            if kind == "prog":
                self.bar_value = v[0] * 100 / v[1]
                self.bar.set(self.bar_value)
                self.set_status("st_work", GOLD, i=v[0], n=v[1])
            else:
                self._done(*v)
                return

    def _work(self, tol, fea, color, glob, opts, outdir, files):
        ok, fail, last = 0, [], None
        used = set()
        n = len(files)
        for i, f in enumerate(files, 1):
            try:
                d = Path(outdir) if outdir else f.parent / "transparent"
                d.mkdir(parents=True, exist_ok=True)
                img = Image.open(f)
                img.load()
                res = rb.postprocess(rb.remove_bg(img, tol, fea, color, glob), opts)
                res.save(rb.unique_dst(d, f, used))
                last = d
                ok += 1
            except Exception:
                fail.append(f"{f.name}: {traceback.format_exc().splitlines()[-1]}")
            self.q.put(("prog", i, n))
        self.q.put(("done", ok, fail, last))

    def _done(self, ok, fail, last):
        self.busy = False
        self.run_btn.config_state("normal", self.tr("start"))
        self.set_status("st_done", MINT if not fail else PINK, ok=ok,
                        extra=self.tr("st_fail", f=len(fail)) if fail else "")
        msg = self.tr("done_msg", ok=ok, d=last) if last else self.tr("done_none")
        if fail:
            msg += "\n\n" + self.tr("done_fails") + "\n" + "\n".join(fail[:5])
        if last and messagebox.askyesno(self.tr("done_title"), msg + "\n\n" + self.tr("open_q")):
            os.startfile(last)
        elif not last:
            messagebox.showerror(self.tr("err_title"), msg)

    # ------------------------------------------------------------ 설정 창
    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        win = tk.Toplevel(self)
        self.settings_win = win
        win.title(self.tr("set_title"))
        win.configure(bg=BG)
        win.transient(self)
        f10 = F(10)

        tk.Label(win, text=self.tr("settings"), bg=BG, fg=GOLD, font=F(16)).pack(pady=(sc(10), sc(4)))
        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True, padx=sc(14))

        # 언어
        cl = Card(body, None, self.tr("set_lang"), SKY)
        cl.pack(fill="x", pady=(0, sc(8)))
        lr = tk.Frame(cl.body, bg=PANEL)
        lr.pack(fill="x")
        for code, name in LANGS:
            on = code == self.cfg["lang"]
            GameButton(lr, name, lambda c=code: self._set_lang(c),
                       GOLD if on else INACTIVE, GOLD_D if on else INACTIVE_D, DARK if on else TEXT,
                       height=36, font=f10).pack(side="left", padx=(0, sc(6)))

        # 캐시
        cc = Card(body, None, self.tr("set_cache"), PINK)
        cc.pack(fill="x", pady=(0, sc(8)))
        info = tk.Label(cc.body, text=self.tr("set_cache_info", s=fmt_size(cache_size())), bg=PANEL, fg=SUB,
                        font=F(9, False), anchor="w", justify="left", wraplength=sc(430))
        info.pack(fill="x")

        def do_clear():
            before = cache_size()
            clear_cache()
            info.config(text=self.tr("set_cache_done", s=fmt_size(before)) + "\n" +
                        self.tr("set_cache_info", s=fmt_size(cache_size())).split("\n")[0])
        GameButton(cc.body, self.tr("set_cache_btn"), do_clear, PINK, PINK_D, TEXT, height=34, font=f10).pack(
            anchor="w", pady=(sc(4), 0))

        # 저장 경로
        cs = Card(body, None, self.tr("set_save"), MINT)
        cs.pack(fill="x", pady=(0, sc(8)))
        cur = tk.Label(cs.body, text="", bg=PANEL, fg=TEXT, font=F(9, False), anchor="w", justify="left",
                       wraplength=sc(430))
        cur.pack(fill="x")

        def refresh():
            cur.config(text=self.tr("set_current") + "\n" + (self.cfg["outdir"] or self.tr("save_default")))
            self._refresh_out_label()

        def change():
            p = filedialog.askdirectory(title=self.tr("dlg_out"), parent=win)
            if p:
                self.cfg["outdir"] = p
                save_settings(self.cfg)
                refresh()

        def reset():
            self.cfg["outdir"] = ""
            save_settings(self.cfg)
            refresh()

        def open_dir():
            if self.cfg["outdir"]:
                d = Path(self.cfg["outdir"])
                d.mkdir(parents=True, exist_ok=True)
                os.startfile(d)
            elif self.files:
                t = self.files[min(self.sel, len(self.files) - 1)].parent / "transparent"
                os.startfile(t if t.exists() else t.parent)
        br = tk.Frame(cs.body, bg=PANEL)
        br.pack(fill="x", pady=(sc(4), 0))
        GameButton(br, self.tr("set_change"), change, SKY, SKY_D, DARK, height=34, font=f10).pack(side="left")
        GameButton(br, self.tr("set_reset"), reset, GOLD, GOLD_D, DARK, height=34, font=f10).pack(
            side="left", padx=sc(6))
        GameButton(br, self.tr("set_open"), open_dir, MINT, MINT_D, DARK, height=34, font=f10).pack(side="left")
        refresh()

        tk.Label(win, text=self.tr("set_saved"), bg=BG, fg=SUB, font=F(9, False)).pack()
        GameButton(win, self.tr("set_close"), win.destroy, GOLD, GOLD_D, DARK, width=140, height=38,
                   font=f10).pack(pady=(sc(4), sc(10)))

        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 8, win.winfo_reqheight() + 4
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        win.grab_set()

    def _set_lang(self, code):
        self.cfg["lang"] = code
        save_settings(self.cfg)
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.destroy()
        self.rebuild()
        self.open_settings()


def selftest(out_path):
    """빌드 검증용: 라이브러리/폰트/드래그앤드롭/엔진이 번들에 제대로 들어갔는지 점검."""
    res = {"frozen": FROZEN, "pixel_font": PIXEL, "dnd": DND_FILES is not None}
    try:
        app = App()
        app.update()
        res["galmuri_family"] = _family("Galmuri11")
        res["scale"] = S
        img = Image.new("RGB", (60, 60), (0, 200, 0))
        from PIL import ImageDraw
        ImageDraw.Draw(img).ellipse((15, 15, 45, 45), fill=(200, 30, 30))
        out = rb.remove_bg(img)
        res["engine_ok"] = out.getpixel((0, 0))[3] == 0 and out.getpixel((30, 30))[3] == 255
        res["icon_loaded"] = hasattr(app, "_icon")
        o = rb.default_opts()
        o.update(resize="scale", scale=200, method="nearest", canvas=(64, 64))
        res["post_ok"] = rb.postprocess(out, o).size == (64, 64)
        app.destroy()
    except Exception:
        res["error"] = traceback.format_exc()
    Path(out_path).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(sys.argv[sys.argv.index("--selftest") + 1])
    else:
        try:
            App().mainloop()
        except Exception:
            log_error(traceback.format_exc())
            raise
