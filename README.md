# 배경 지우개 (BG Eraser)

게임 에셋·리소스 이미지의 **배경을 자동으로 투명화**하는 도트 감성 GUI 프로그램입니다.
Windows용 **exe 한 개**로 실행됩니다. (파이썬·별도 설치 필요 없음)

## 다운로드 · 실행
1. [Releases](../../releases/latest)에서 **`BG-Eraser.exe`** 를 받습니다.
2. 원하는 폴더에 두고 더블클릭! (처음 실행은 압축을 푸느라 몇 초 걸립니다)

> **Windows가 "PC를 보호했습니다"라고 막을 때**
> 서명되지 않은 개인 제작 프로그램이라 나오는 안내입니다. **추가 정보 → 실행**을 누르면 됩니다.

- 설정(`settings.json`)과 오류 기록(`error_log.txt`)은 exe와 같은 폴더에 저장됩니다.
- exe 아이콘 위로 이미지·폴더를 끌어다 놓아도 바로 담깁니다.

## 특징
- 테두리에서 이어진 배경만 자동 감지해 제거 (그림 안쪽의 같은 색은 보존 옵션)
- 안티에일리어싱 경계의 배경색 섞임(헤일로) 복원, 도트 그래픽용 또렷한 모드
- 실시간 미리보기 (체크무늬 = 투명), 배경색 직접 지정, 투명 여백 자르기
- 여러 장/폴더 일괄 처리, 끌어다 놓기 지원, 같은 이름 파일 자동 구분
- 창 크기에 맞춰 UI 전체가 비율대로 확대/축소
- 설정: 언어(한국어 / English / 日本語 / 中文), 캐시 정리, 자동 저장 경로
- [갈무리(Galmuri)](https://github.com/quiple/galmuri) 도트 폰트 사용

## 소스로 실행 / exe 직접 빌드
[uv](https://docs.astral.sh/uv/)가 필요합니다.
```
# 소스로 바로 실행
uv run src/remove_bg_gui.pyw

# exe 빌드 -> dist/BG-Eraser.exe
build_exe.bat

# 명령줄(CLI)로 일괄 처리
uv run src/remove_bg.py 이미지.png 폴더 -r -o out --trim
```
CLI 옵션: `-t` 허용 오차, `-f` 경계 부드러움(0=또렷), `-c` 배경색, `--global`, `--trim`, `--pad`, `-r`, `--overwrite`

## 구성
```
build_exe.bat      exe 빌드 스크립트 (PyInstaller)
src/               소스 (remove_bg_gui.pyw = GUI, remove_bg.py = 엔진 + CLI)
assets/            아이콘 (tools/make_icon.py 로 생성)
fonts/             Galmuri (SIL OFL 1.1)
사용법.txt         사용 안내
```

## 라이선스
폰트 Galmuri는 SIL Open Font License 1.1 (`fonts/Galmuri_라이선스(OFL).txt`)을 따릅니다.
