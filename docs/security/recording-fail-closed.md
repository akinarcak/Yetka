# Recording fail-closed policy

Replay metadata and parts are security evidence. An upload task must report a
failure when the source session/part is missing or remote storage rejects the
upload. Local evidence is deleted only after a confirmed successful upload.
Consumers must not expose a partial replay as complete; operators should
retry or restore from the retained local evidence according to the production
checklist.
