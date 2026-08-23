# audiovisual

## Generating the library

Each family emitter writes its entire catalog. `generate_all_in_repo.py` runs every `*_generator.py`.

```bash
python generate_all_in_repo.py          # entire library
python neutrik/neutrik_generator.py     # one family
python neutrik/neutrik_generator.py --csv-only
python check.py                         # CI merge gate
```

Harness scripts import `neutrik.py` (the chooser), not the generator.