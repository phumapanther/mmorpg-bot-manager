# ติดตั้ง/อัปเดต BotManager แบบไม่ต้องสิทธิ์แอดมิน (per-user) — คัดลอกไฟล์ + สร้างช็อตคัต + ลงทะเบียนใน Add/Remove Programs
# รันสคริปต์นี้ซ้ำได้เสมอเพื่ออัปเดตเป็นเวอร์ชันใหม่ — จะทับแค่ BotManager.exe เท่านั้น
# ไม่แตะ config.json / game_data.db ของลูกค้าเลย (ไฟล์พวกนี้ไม่ได้อยู่ในชุดติดตั้ง สร้าง/แก้โดยตัวโปรแกรมเองตอนรัน)
$ErrorActionPreference = "Stop"

$SourceDir = $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA "BotManager"
$IsUpdate = Test-Path (Join-Path $InstallDir "config.json")

if ($IsUpdate) {
    Write-Host "พบการติดตั้งเดิมอยู่แล้ว — กำลังอัปเดต BotManager (ตั้งค่า/ข้อมูลผู้เล่นเดิมจะไม่หาย) ..."
} else {
    Write-Host "กำลังติดตั้ง BotManager ไปที่ $InstallDir ..."
}

# ปิดโปรแกรมก่อนถ้ากำลังรันอยู่ ไม่งั้น Windows จะทับไฟล์ .exe ที่กำลังใช้งานไม่ได้
Get-Process -Name "BotManager" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Copy-Item -Path (Join-Path $SourceDir "BotManager.exe") -Destination $InstallDir -Force
# config.example.json คือไฟล์เทมเพลต/ค่าเริ่มต้นของแอป (ไม่ใช่ค่าที่ลูกค้าตั้งเอง) ต้องอัปเดตทุกครั้งให้ตรงเวอร์ชันใหม่
# ค่าที่ลูกค้าตั้งเองอยู่ใน config.json ซึ่งเป็นคนละไฟล์ ไม่ถูกแตะเลย
Copy-Item -Path (Join-Path $SourceDir "config.example.json") -Destination $InstallDir -Force
Copy-Item -Path (Join-Path $SourceDir "uninstall.ps1") -Destination $InstallDir -Force

$ExePath = Join-Path $InstallDir "BotManager.exe"
$Shell = New-Object -ComObject WScript.Shell

$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartShortcut = $Shell.CreateShortcut((Join-Path $StartMenuDir "BotManager.lnk"))
$StartShortcut.TargetPath = $ExePath
$StartShortcut.WorkingDirectory = $InstallDir
$StartShortcut.IconLocation = $ExePath
$StartShortcut.Save()

$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = $Shell.CreateShortcut((Join-Path $DesktopPath "BotManager.lnk"))
$DesktopShortcut.TargetPath = $ExePath
$DesktopShortcut.WorkingDirectory = $InstallDir
$DesktopShortcut.IconLocation = $ExePath
$DesktopShortcut.Save()

$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BotManager"
New-Item -Path $UninstallKey -Force | Out-Null
Set-ItemProperty -Path $UninstallKey -Name "DisplayName" -Value "BotManager"
Set-ItemProperty -Path $UninstallKey -Name "UninstallString" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
Set-ItemProperty -Path $UninstallKey -Name "DisplayIcon" -Value $ExePath
Set-ItemProperty -Path $UninstallKey -Name "Publisher" -Value "BotManager"
Set-ItemProperty -Path $UninstallKey -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $UninstallKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $UninstallKey -Name "NoRepair" -Value 1 -Type DWord

Write-Host ""
if ($IsUpdate) {
    Write-Host "อัปเดตสำเร็จ! ตั้งค่า/ข้อมูลผู้เล่นเดิมยังอยู่ครบ เปิดโปรแกรมได้จาก Start Menu หรือไอคอนบน Desktop"
} else {
    Write-Host "ติดตั้งสำเร็จ! เปิดโปรแกรมได้จาก Start Menu หรือไอคอนบน Desktop (ชื่อ BotManager)"
    Write-Host "ถอนการติดตั้งได้ผ่าน Windows Settings > Apps > BotManager > Uninstall"
}
