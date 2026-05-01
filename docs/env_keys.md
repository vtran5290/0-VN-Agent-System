# API keys & env (local only)

**Không commit file chứa key thật.** Dùng `.env` ở repo root (đã thêm vào `.gitignore`).

## FRED_API_KEY

- **Dùng cho:** `python -m src.macro.fred_fetch_us_fiscal_stress`, auto-fill UST/DXY trong weekly.
- **Lấy key:** [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) — đăng ký free.
- **Lưu local:** Trong `.env` đặt dòng:
  ```bash
  FRED_API_KEY=<your_key>
  ```
- **Chạy lệnh (từ repo root):**
  ```bash
  # Windows PowerShell — load .env rồi chạy
  Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } }
  python -m src.macro.fred_fetch_us_fiscal_stress --asof 2026-02-20
  # Hoặc set tay một lần:
  $env:FRED_API_KEY = "your_key"
  python -m src.macro.fred_fetch_us_fiscal_stress --asof 2026-02-20
  ```
  ```bash
  # Linux/macOS
  set -a && source .env && set +a
  python -m src.macro.fred_fetch_us_fiscal_stress --asof 2026-02-20
  ```

Key hiện tại đã được lưu trong `.env` (chỉ tồn tại trên máy bạn, không đẩy lên git).
