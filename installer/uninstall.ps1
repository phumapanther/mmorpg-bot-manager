# ถอนการติดตั้ง BotManager — ลบช็อตคัต/ทะเบียน แต่ "ไม่ลบ" config.json และ game_data.db (กันข้อมูลผู้เล่นหาย)
$ErrorActionPreference = "SilentlyContinue"

$InstallDir = Join-Path $env:LOCALAPPDATA "BotManager"

Get-Process -Name "BotManager" | Stop-Process -Force

Remove-Item -Path (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\BotManager.lnk") -Force
Remove-Item -Path (Join-Path ([Environment]::GetFolderPath("Desktop")) "BotManager.lnk") -Force
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BotManager" -Recurse -Force
Remove-Item -Path (Join-Path $InstallDir "BotManager.exe") -Force

Write-Host "ถอนการติดตั้ง BotManager เรียบร้อยแล้ว"
Write-Host "หมายเหตุ: ไฟล์ config.json และฐานข้อมูลผู้เล่น (game_data.db) ยังอยู่ที่ $InstallDir"
Write-Host "ถ้าต้องการลบข้อมูลทั้งหมดจริงๆ ให้ลบโฟลเดอร์นี้ด้วยตัวเอง"
Start-Sleep -Seconds 5
