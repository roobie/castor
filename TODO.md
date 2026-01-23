# TODO

### Be able to add blob to store from stdin:

`curl https://example.org | casq add --ref-name example-dot-org@20260123 -`

---

### Add support for -j/--json and/or --jsonl to enable machine readable output, e.g.

```bash
casq ls --jsonl
# {"ref": "some-blob", "hash": "abc123...", "hashAlgo": "blake3-256"}

# so one can do:
casq ls --jsonl | jq -cs '.[].hash' | ...
```

---
