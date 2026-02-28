# Convert 2 Gil books (epub/mobi) from Downloads to docs/books/*.md
# Chạy sau khi đã cài Calibre (ebook-convert có trong PATH).
# Hoặc sửa $calibre thành đường dẫn đầy đủ tới ebook-convert.exe (vd. "C:\Program Files\Calibre2\ebook-convert.exe")

$ErrorActionPreference = "Stop"
$Downloads = "c:\Users\LOLII\Downloads"
$Repo = "c:\Users\LOLII\Documents\V\0. VN Agent System"
$Books = Join-Path $Repo "docs\books"

$epub = Join-Path $Downloads "In The Trading Cockpit with the O'Neil Disciples _ -- Morales, Gil; Kacher, Chris -- 1, FR, 2012 -- John Wiley & Sons, Incorporated -- 9781118273029 -- 6c28d654ac9bff7cac8d9d6f96fea7e9 -- Anna's Archive.epub"
$mobi = Join-Path $Downloads "Trade Like an O'Neil Disciple -- Gil Morales & Chris Kacher [Kacher, Chris] -- 2010 -- Wiley -- 6b29345a98bd1cd4b2821e289a169671 -- Anna's Archive.mobi"

$out2012 = Join-Path $Books "gil_2012_trading_cockpit.md"
$out2010 = Join-Path $Books "gil_2010_trade_like_oneil_disciple.md"

# Try Calibre: PATH first, then common install path
$exe = $null
try {
  $exe = (Get-Command ebook-convert -ErrorAction Stop).Source
} catch {
  if (Test-Path "C:\Program Files\Calibre2\ebook-convert.exe") {
    $exe = "C:\Program Files\Calibre2\ebook-convert.exe"
  }
}
if (-not $exe) {
  Write-Host "Calibre (ebook-convert) chua cai hoac chua co trong PATH."
  Write-Host "Cai Calibre tu https://calibre-ebook.com hoac chay thu cong 2 lenh sau (sau khi cai):"
  Write-Host ""
  Write-Host "ebook-convert `"$mobi`" `"$out2010`""
  Write-Host "ebook-convert `"$epub`" `"$out2012`""
  exit 1
}

if (-not (Test-Path $mobi)) { Write-Host "Khong tim thay: $mobi"; exit 1 }
if (-not (Test-Path $epub)) { Write-Host "Khong tim thay: $epub"; exit 1 }

Write-Host "Converting 2010 (mobi) -> gil_2010_trade_like_oneil_disciple.md ..."
& $exe $mobi $out2010
Write-Host "Converting 2012 (epub) -> gil_2012_trading_cockpit.md ..."
& $exe $epub $out2012
Write-Host "Done. Kiem tra: $Books"
exit 0
