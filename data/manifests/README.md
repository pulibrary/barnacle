# Manifest Lists for Batch Processing

This directory contains the master list of IIIF manifest URLs and pre-split tranches for distributed processing across HPC and VM environments.

## Files

| File | Lines | Description |
|------|-------|-------------|
| `all.txt` | 2,853 | Complete list of all manifest URLs |
| `tranche-01.txt` | 500 | URLs 1-500 |
| `tranche-02.txt` | 500 | URLs 501-1000 |
| `tranche-03.txt` | 500 | URLs 1001-1500 |
| `tranche-04.txt` | 500 | URLs 1501-2000 |
| `tranche-05.txt` | 500 | URLs 2001-2500 |
| `tranche-06.txt` | 353 | URLs 2501-2853 |

## Work Assignment

| Location | Tranches | Manifests | Output Directory |
|----------|----------|-----------|------------------|
| HPC (Tufts) | 1-5 | 2,500 | TBD (see HPC storage docs) |
| VM | 6 | 353 | `~/barnacle-output` |

## Usage

### Processing a Tranche

```bash
# On HPC - process tranches 1-5
barnacle run data/manifests/tranche-01.txt <OUTPUT_DIR>
barnacle run data/manifests/tranche-02.txt <OUTPUT_DIR>
# ... etc

# On VM - process tranche 6
barnacle run data/manifests/tranche-06.txt ~/barnacle-output
```

### Testing

```bash
# Smoke test with limited pages
barnacle run data/manifests/tranche-01.txt output/ --max-pages 1
```

### Re-splitting

If you need different tranche sizes, use `all.txt` as the source:

```bash
# Example: split into tranches of 1000
split -l 1000 -d -a 2 all.txt tranche-
for f in tranche-*; do mv "$f" "${f}.txt"; done
```

## Notes

- Output files are named using SHA1 hash of manifest URL, so tranches can be re-run safely
- The `--resume` flag (enabled by default) allows interrupted processing to continue
- See [batch-processing.md](../../docs/batch-processing.md) for full documentation

## HPC Output Path

Before running on HPC, determine the appropriate output directory:

1. **Project allocation**: Ask HPC admins about `/project/<project_name>/` space
2. **Research storage**: Check for `/cluster/tufts/` or similar research allocations
3. **Home directory**: `$HOME/barnacle-output/` (check quota with `quota -s`)

Run `df -h` on the HPC to see available filesystems, or consult [Tufts HPC storage documentation](https://it.tufts.edu/high-performance-computing).
