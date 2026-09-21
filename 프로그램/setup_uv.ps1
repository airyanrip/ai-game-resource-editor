# uv(파이썬 실행 도구)가 없을 때 설치를 도와주는 안내 창.
# 배경투명화.bat 이 uv를 못 찾으면 자동으로 호출한다.
# 종료 코드: 0 = uv 준비됨(설치 완료), 1 = 실패, 2 = 설치 페이지로 이동함, 3 = 취소
param([string]$Choice = "", [switch]$DryRun)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PageUrl = "https://docs.astral.sh/uv/getting-started/installation/"
$UvExe = Join-Path $env:USERPROFILE ".local\bin\uv.exe"

# 언어: 프로그램 설정(settings.json) -> 없으면 윈도우 언어
$lang = ""
try {
    $sf = Join-Path (Split-Path $PSScriptRoot -Parent) "settings.json"
    if (Test-Path $sf) { $lang = (Get-Content $sf -Raw -Encoding UTF8 | ConvertFrom-Json).lang }
} catch {}
if (-not $lang) { $lang = (Get-UICulture).TwoLetterISOLanguageName }
if ($lang -notin @("ko", "en", "ja", "zh")) { $lang = "en" }

$M = @{
    ko = @{
        title = "배경 지우개 - 준비가 필요해요"
        ask   = "이 프로그램을 실행하려면 무료 도구 'uv'가 필요해요.`n(파이썬과 필요한 부품을 자동으로 준비해 주는 도구예요)`n`n지금 자동으로 설치할까요?`n`n  [예]        자동 설치 (인터넷 필요, 1~2분)`n  [아니오]  설치 페이지 열기 (직접 설치)`n  [취소]     닫기"
        busy  = "uv 설치 중… 잠시만 기다려 주세요 (1~2분)"
        done  = "설치가 끝났어요! 배경 지우개를 바로 시작할게요."
        fail  = "자동 설치에 실패했어요. (인터넷 연결을 확인해 주세요)`n설치 페이지를 열어 드릴게요.`n`n설치 후 '배경투명화.bat'을 다시 실행해 주세요."
        guide = "설치 페이지를 열었어요.`n`n[설치 방법]`n1) 페이지에서 Windows 항목의 명령어를 복사`n    (powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`")`n2) 시작 메뉴에서 'PowerShell'을 열고 붙여넣기 → Enter`n3) 설치가 끝나면 '배경투명화.bat'을 다시 실행`n`n또는 명령 프롬프트에서:  winget install --id=astral-sh.uv -e"
    }
    en = @{
        title = "BG Eraser - Setup needed"
        ask   = "This program needs a free tool called 'uv'.`n(It prepares Python and the required parts automatically.)`n`nInstall it automatically now?`n`n  [Yes]     Automatic install (internet required, 1-2 min)`n  [No]      Open the install page (install by hand)`n  [Cancel]  Close"
        busy  = "Installing uv... please wait (1-2 min)"
        done  = "Installed! Starting BG Eraser."
        fail  = "Automatic install failed. (Please check your internet connection)`nOpening the install page for you.`n`nAfter installing, run the launcher .bat again."
        guide = "The install page is open.`n`n[How to install]`n1) Copy the Windows command from the page`n    (powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`")`n2) Open 'PowerShell' from the Start menu, paste it, press Enter`n3) When it finishes, run the launcher .bat again`n`nOr in a terminal:  winget install --id=astral-sh.uv -e"
    }
    ja = @{
        title = "背景消しゴム - 準備が必要です"
        ask   = "このプログラムを実行するには、無料ツール「uv」が必要です。`n(Pythonと必要な部品を自動で用意してくれるツールです)`n`n今すぐ自動でインストールしますか?`n`n  [はい]      自動インストール (ネット接続が必要、1~2分)`n  [いいえ]   インストールページを開く (手動)`n  [キャンセル] 閉じる"
        busy  = "uvをインストール中… しばらくお待ちください (1~2分)"
        done  = "インストール完了! 背景消しゴムを起動します。"
        fail  = "自動インストールに失敗しました。(ネット接続をご確認ください)`nインストールページを開きます。`n`nインストール後、もう一度起動用の .bat を実行してください。"
        guide = "インストールページを開きました。`n`n[インストール方法]`n1) ページのWindows用コマンドをコピー`n    (powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`")`n2) スタートメニューから「PowerShell」を開いて貼り付け → Enter`n3) 終わったら起動用の .bat をもう一度実行`n`nまたはコマンドで:  winget install --id=astral-sh.uv -e"
    }
    zh = @{
        title = "背景橡皮擦 - 需要先做准备"
        ask   = "运行本程序需要免费工具 'uv'。`n(它会自动准备 Python 和所需组件)`n`n现在自动安装吗？`n`n  [是]    自动安装 (需要联网，约 1~2 分钟)`n  [否]    打开安装页面 (手动安装)`n  [取消]  关闭"
        busy  = "正在安装 uv… 请稍候 (约 1~2 分钟)"
        done  = "安装完成！马上启动背景橡皮擦。"
        fail  = "自动安装失败。(请检查网络连接)`n将为你打开安装页面。`n`n安装后请重新运行启动用的 .bat 文件。"
        guide = "已打开安装页面。`n`n[安装方法]`n1) 复制页面上 Windows 的命令`n    (powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`")`n2) 从开始菜单打开 'PowerShell'，粘贴后按 Enter`n3) 完成后重新运行启动用的 .bat 文件`n`n或在终端中:  winget install --id=astral-sh.uv -e"
    }
}[$lang]

# 항상 맨 앞에 뜨는 소유 창 (bat 창이 최소화돼 있어도 안내가 가려지지 않게)
$owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false;
    StartPosition = "CenterScreen"; Size = New-Object System.Drawing.Size(1, 1); Opacity = 0 }
$owner.Show()

function Ask([string]$text, [string]$buttons, [string]$icon) {
    if ($DryRun) { Write-Host "[dialog:$buttons] $text"; return "OK" }
    return [System.Windows.Forms.MessageBox]::Show($owner, $text, $M.title,
        [System.Windows.Forms.MessageBoxButtons]::$buttons, [System.Windows.Forms.MessageBoxIcon]::$icon)
}

function Install-Uv {
    if ($DryRun) { return $true }
    $pw = New-Object System.Windows.Forms.Form -Property @{ Text = $M.title; TopMost = $true;
        StartPosition = "CenterScreen"; Size = New-Object System.Drawing.Size(460, 110);
        FormBorderStyle = "FixedDialog"; ControlBox = $false }
    $lb = New-Object System.Windows.Forms.Label -Property @{ Text = $M.busy; AutoSize = $false;
        Dock = "Fill"; TextAlign = "MiddleCenter" }
    $pw.Controls.Add($lb); $pw.Show(); [System.Windows.Forms.Application]::DoEvents()
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression *> $null
    } catch {}
    $pw.Close()
    return (Test-Path $UvExe) -or [bool](Get-Command uv -ErrorAction SilentlyContinue)
}

if ($Choice -eq "") {
    $r = Ask $M.ask "YesNoCancel" "Question"
    $Choice = @{ Yes = "Yes"; No = "No"; Cancel = "Cancel" }["$r"]
}

switch ($Choice) {
    "Yes" {
        if (Install-Uv) {
            if ($Choice -eq "Yes" -and -not $DryRun) { [void](Ask $M.done "OK" "Information") }
            $owner.Close(); exit 0
        }
        if (-not $DryRun) { Start-Process $PageUrl }
        [void](Ask $M.fail "OK" "Warning"); $owner.Close(); exit 1
    }
    "No" {
        if (-not $DryRun) { Start-Process $PageUrl }
        [void](Ask $M.guide "OK" "Information"); $owner.Close(); exit 2
    }
    default { $owner.Close(); exit 3 }
}
