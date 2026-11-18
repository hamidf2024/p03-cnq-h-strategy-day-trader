# chats/raw/

The complete, unedited session event log, gzip-compressed and split into parts
(GitHub's web upload limit is 25 MB per file). To restore and verify:

```bash
cat session-01-events.json.gz.part-* > session-01-events.json.gz
shasum -a 256 -c session-01-events.json.gz.sha256
gunzip -k session-01-events.json.gz
```
