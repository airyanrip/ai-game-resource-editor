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
`배경투명화.bat`을 더블클릭하면 됩니다.

**uv가 없다면?** 처음 실행할 때 안내 창이 자동으로 떠서 도와줍니다.
- **[예]** 자동 설치 (인터넷 필요, 1~2분) → 끝나면 바로 실행됩니다.
- **[아니오]** [설치 페이지](https://docs.astral.sh/uv/getting-started/installation/)를 열어 줍니다.

직접 설치하려면 PowerShell에서 아래 한 줄을 실행한 뒤 `배경투명화.bat`을 다시 실행하세요.
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
또는 `winget install --id=astral-sh.uv -e`

> [uv](https://docs.astral.sh/uv/)는 Python과 필요한 라이브러리를 자동으로 준비해 주는 무료 도구입니다.
> 처음 한 번은 필요한 부품을 내려받느라 몇 초~1분 걸립니다.

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
  setup_uv.ps1        uv가 없을 때 설치를 도와주는 안내 창
폰트/                 Galmuri (SIL OFL 1.1)
```

## 라이선스
폰트 Galmuri는 SIL Open Font License 1.1 (`폰트/Galmuri_라이선스(OFL).txt`)을 따릅니다.
