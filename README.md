# 배경 지우개 (BG Eraser)

게임 에셋·리소스 이미지의 **배경을 자동으로 투명화**하는 도트 감성 GUI 프로그램입니다.
Windows + Python(uv)으로 동작하며, 컴퓨터를 잘 몰라도 쓸 수 있게 만들었습니다.

## 특징
- 테두리에서 이어진 배경만 자동 감지해 제거 (그림 안쪽의 같은 색은 보존 옵션)
- 안티에일리어싱 경계의 배경색 섞임(헤일로) 복원, 도트 그래픽용 또렷한 모드
- 실시간 미리보기 (체크무늬 = 투명), 배경색 직접 지정, 투명 여백 자르기
- 여러 장/폴더 일괄 처리, 끌어다 놓기 지원, 같은 이름 파일 자동 구분
- 창 크기에 맞춰 UI 전체가 비율대로 확대/축소
- 설정: 언어(한국어 / English / 日本語 / 中文), 캐시 정리, 자동 저장 경로
- [갈무리(Galmuri)](https://github.com/quiple/galmuri) 도트 폰트 사용

## 실행
1. [uv](https://docs.astral.sh/uv/) 설치 (Python과 필요한 라이브러리를 자동으로 준비해 줍니다)
2. `배경투명화.bat` 더블클릭

명령줄로도 쓸 수 있습니다.
```
uv run 프로그램/remove_bg.py 이미지.png 폴더 -r -o out --trim
```
옵션: `-t` 허용 오차, `-f` 경계 부드러움(0=또렷), `-c` 배경색, `--global`, `--trim`, `--pad`, `-r`, `--overwrite`

## 구성
```
배경투명화.bat        실행 파일
사용법.txt            사용 안내
프로그램/
  remove_bg_gui.pyw   GUI
  remove_bg.py        배경 제거 엔진 + CLI
폰트/                 Galmuri (SIL OFL 1.1)
```

## 라이선스
폰트 Galmuri는 SIL Open Font License 1.1 (`폰트/Galmuri_라이선스(OFL).txt`)을 따릅니다.
