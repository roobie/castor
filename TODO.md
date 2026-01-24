# TODO

### Add support for --json to enable machine readable output, e.g.

```bash
casq ls --json
# {"ref": "some-blob", "hash": "abc123...", "hashAlgo": "blake3-256"}

# so one can do:
casq ls --jsonl | jq -cs '.[].hash' | ...
```

---
