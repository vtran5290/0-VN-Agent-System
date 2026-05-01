---
name: thermal-coretemp-parallel-gate
description: >-
  Reads CPU temperature from Core Temp (ALCPU GetCoreTempInfo.dll / shared memory)
  and gates parallel agent work (subprocess batches, dual heavy jobs). Use when
  launching long CPU-bound Windows tasks, parallel backtests, background shells,
  grid searches, or when the user mentions Core Temp, CPU temperature, thermal
  throttle, overheating, or serializing workloads.
---

# Thermal gate (Core Temp) for parallel work

## Facts vs limits

- **FACT:** Core Temp exposes data to other processes via **GetCoreTempInfo.dll** and the documented **CoreTempSharedDataEx** layout (see https://alcpu.com/CoreTemp/developers.html).
- **FACT:** The Cursor agent is **not** a Windows driver and cannot “plug into” the Core Temp GUI thermostat control as a native plugin. Use **read temperature → change behavior** instead.
- **LIMIT:** **DLL bitness must match Python** (64-bit Python needs 64-bit `GetCoreTempInfo.dll`). If read fails, fall back to **single worker** and tell the user to fix DLL path or Core Temp not running.

## One-shot read (agent step)

From repo root:

```bash
python .cursor/skills/thermal-coretemp-parallel-gate/scripts/coretemp_read.py --json
```

Optional: `CORE_TEMP_INFO_DLL=C:/path/to/GetCoreTempInfo.dll` if the DLL is not next to the script and not under `Program Files/Core Temp/`.

Interpret `max_temp` and `unit` (`C` or `F`). If `ok` is false, **assume unknown temp** → prefer **one** heavy child process at a time.

## Thermostat policy (default numbers, user-tunable)

Use env overrides when the user names different comfort limits.

| Zone | Default (°C) | Agent behavior |
|------|----------------|----------------|
| Cool | max_temp < 75 | Up to **2** concurrent heavy jobs if the user asked for parallel. |
| Warm | 75–84 | **1** heavy job; queue the other. |
| Hot | ≥ 85 | **0** new heavy jobs until cool: `Start-Sleep -Seconds 60`, re-poll; or shrink batch size / `--batch-size`. |

If the user reports **Fahrenheit** in Core Temp, convert thresholds or compare against `unit == "F"` (e.g. 85 °C ≈ 185 °F).

## Where to poll

- **Before** starting `N` parallel `python` / `research_*` runs.
- **Between** checkpoint tries (after each `try_XX` completes) for multi-hour grids.
- **After** any job was killed for “unknown exit” / watchdog — re-poll before restart.

## Integration pattern (no repo refactor required)

1. Run `coretemp_read.py --json`.
2. Decide `max_parallel` (0/1/2) from the table.
3. Launch only `max_parallel` children; hold the rest until the next poll shows cool enough.

For **existing** scripts without an internal gate, the agent should **serialize** at the orchestration layer (fewer simultaneous terminal commands), not rewrite unrelated research code unless the user asks.

## When Core Temp is unavailable

If JSON says `ok: false`:

1. State **Unknown** temperature and the reason (missing DLL, Core Temp not running, bitness mismatch).
2. Default to **serial** heavy runs or smaller batches.
3. List what would fix it: install Core Temp, copy matching `GetCoreTempInfo.dll`, set `CORE_TEMP_INFO_DLL`.
