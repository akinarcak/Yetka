# Recording fail-closed lifecycle

Replay recording has three states: local capture, external replication, and
availability. A local file is the durable source until external replication
reports success. The upload worker deletes the local copy only after the
external storage returns success; missing sessions, missing parts, and upload
errors raise `ReplayUploadError` and retain the local file for retry/recovery.

Replay metadata is authoritative for multipart recordings. Missing or empty
metadata, or any missing part referenced by it, fails the download operation;
the API must return an unavailable/error response rather than marking the
session replay as available or producing a partial archive.

The invariant is: no successful upload acknowledgement means no destructive
cleanup, and no complete metadata-plus-parts set means no replay download.
Tests in `apps/terminal/recording_tests.py` lock these failure semantics.
