# Car-hunt standard forms

Reusable, **vehicle-agnostic** documents for any used-car purchase. These don't
change per car, so they live with the skill (unlike per-car test-drive checklists,
which are generated on demand and stored in the cloud folder named in
`config/household.yaml` — see `../references/test-drive.md`, Step 5.5).

**Jurisdiction example:** the bill of sale and the fraud checklist's title-transfer
section use **Alabama** as one state's worked example. Edit the state-specific lines
in `build_forms.py` (search for "Alabama") to match your state before relying on
them. Public copies of this skill ship without the PDFs — run the generator once.

| File | What it is |
|---|---|
| `fraud-paperwork-checklist.pdf` | Title / VIN / curbstoning / odometer / payment fraud checklist — use in the driveway with the title in hand |
| `bill-of-sale-alabama.pdf` | Fillable motor-vehicle bill of sale, Alabama as the example state (seller's copy + buyer's copy), with odometer disclosure and AS-IS language |
| `build_forms.py` | Generator for both PDFs (reportlab). Run to refresh the templates. |

## Regenerate

```bash
python3 build_forms.py    # rewrites both PDFs next to this script
```

Requires `reportlab` (`pip3 install reportlab`) and the DejaVu fonts (for the ☐
checkbox glyph).
