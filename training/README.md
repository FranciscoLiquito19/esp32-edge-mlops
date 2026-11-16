# training

Host-side half of the loop: dataset tooling, training, quantisation and model
packaging. Nothing here runs on the microcontroller.

Code lands with the milestones (see `docs/ROADMAP.md`):

| Path | Purpose | Milestone |
|---|---|---|
| `ingest.py` | Copy captures and metadata from the SD card into `data/raw/` | M2 |
| `data/` | Dataset, tracked with DVC (only `.dvc` pointers are in git) | M2 |
| `train.py` | Train the float32 baseline | M3 |
| `quantize.py` | int8 post-training quantisation and evaluation gate | M3 |
| `package.py` | Wrap the model with its manifest for the `model` partition | M4 |
| `models/` | Exported models (not in git) and evaluation reports | M3 |

## Labels

`person`, `animal`, `nothing`.
