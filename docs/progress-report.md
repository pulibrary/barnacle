# Lapidus OCR Progress Report

*Date: 2026-03-09*

---

## 1. Progress

We are roughly halfway through the corpus. Of 2,852 manifests in scope, 1,447 have been
completed (~50.7%). Pages completed are approximately 199,658 of 420,133 total (~47.5%).

### Summary table

| Tranche | Manifests | Pages  | Status |
|---------|-----------|--------|--------|
| 01      | 500       | 56,730 | Complete |
| 02a     | 249       | 36,117 | Complete (1 skipped — bad manifest on figgy side) |
| 03      | 351       | 54,549 | Complete (349/351; 1 partial set aside, 1 SLURM failure) |
| 04      | 351       | 54,548 | Complete (350/351; Savary vol. 1 resubmitting final ~330 pages) |
| 05–08   | 1,401     | 218,189 | Pending |
| **Total in scope** | **2,852** | **420,133** | |

We have balanced to tranches to include roughly the same number of pages (~350 manifests,
~54,500 pages each), with a maximum estimated run time of 13-17 hours per tranche.

---

## 2. Challenges

### Large volumes and OCR timeouts

A small number of very large items have caused the Kraken OCR engine to time out on
individual pages during processing.

One item has been set aside entirely: a 16th-century compendium of
English statutes (1,859 pages), printed in a Gothic/blackletter
typeface. The model we are using (`catmus-print-fondue-large`) was not
trained on that script and produces unusable output. It will not be
resubmitted. Sasha may wish to review the remaining volumes (see
Section 3) to weed out any other unprocessable books before they are
fed to kraken.


A second large item — Savary's *Universal Dictionary of Trade and Commerce*, vol. 1
(~1,106 pages) — timed out partway through its initial run, completing approximately
775 pages. It has been resubmitted to finish the remaining ~330 pages. The sibling
volume (vol. 2, ~971 pages) is queued in tranche 06 and has not yet been processed.

### Processing tempo

The sheer volume of the corpus (~2,852 manifests, ~420,000 pages) means each tranche
takes 13–17 wall-clock hours on the Tufts HPC cluster. We are submitting tranches
sequentially to be good citizens to the Princeton IIIF server (all manifests resolve
through `figgy.princeton.edu`). As a result, completing the full corpus will span
several additional days of cluster time.

---

## 3. Metadata Resource

The file `data/lapidus_metadata.csv` in this repository provides catalog metadata for
the full corpus. It was generated on 2026-03-06 and contains **2,910 rows** — one per
manifest, with collections expanded into their child manifests (inheriting the parent's
bibliographic identifiers).

### Columns

| Column | Description |
|--------|-------------|
| `manifest_url` | IIIF manifest URL (join key with OCR output) |
| `parent_manifest_url` | Parent collection manifest, if applicable |
| `source_metadata_id` | Princeton catalog identifier |
| `ark` | ARK persistent identifier |
| `dpul_url` | Direct link to the object in DPUL for easy browsing |
| `title` | Title from IIIF metadata |
| `creator` | Creator/author |
| `date` | Date of publication |
| `language` | Language(s) |
| `publisher` | Publisher |
| `extent` | Physical extent |
| `size_cm` | Dimensions |
| `content_type` | Resource type |
| `collections` | Collection memberships |
| `subject` | Subject headings |
| `page_count` | Number of canvases in the manifest |
| `error` | HTTP error code if the manifest was inaccessible |

### Notes

- 56 rows carry `error=HTTP 403` (figgy access restriction). None of these manifests
  appear in the tranche files and no OCR has been attempted for them.
- The `dpul_url` column links directly to each object in DPUL for easy browsing and
  verification.
