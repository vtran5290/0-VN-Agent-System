# Path A Config Registry

| config_name   | ranking_mode     | max_positions | Status              |
|---------------|------------------|---------------|---------------------|
| baseline_old  | current          | 8             | **deprecated**      |
| **champion**  | extension_first  | 8             | **active default**  |
| challenger    | simple_composite | 12            | research            |

- **baseline_old**: Deprecated. Use only for comparison; default Path A run no longer uses this.
- **champion**: Active default. All Path A entry points use Champion unless `--config` is set.
- **challenger**: Research branch. Run with `--config challenger` or via monitoring snapshot for tracking.
