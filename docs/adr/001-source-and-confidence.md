# Confidence is not correctness

Tesseract words retain offsets and image boxes. A field needs a unique, complete labeled OCR span; missing/ambiguous values route to review. Confidence is the minimum word confidence in that field, not a calibrated correctness probability. The default conservative route threshold is fixed before evaluation and remains unchanged even when it routes every measured document to review.

Citation verification checks the value, offsets AND field-label context. Whole-sentence claim matching rejects changed numbers, negation substrings and unsupported paraphrases. It is not semantic/clinical entailment. OCR itself may be wrong even when its own span supports the extraction.

A reviewer can attest to the immutable synthetic source image to correct a missing/wrong OCR value. That is a separate evidence class, not manufactured OCR support. Original OCR stays intact, note/value hashes avoid copying content into audit events, and optimistic revisions prevent concurrent overwrites.

The truth-assisted benchmark exercises this persisted path, but is not a human reviewer study. Human accuracy and time saved remain not measured.

The optional model is a development-set experiment, not a calibrated confidence source. Qwen produced 18/42 correct fields on the fixed six-document subset. Adding explicit template-label hints reduced that to 11/42, so the simpler prompt was restored and rerun. Both raw trials are retained; this comparison is development tuning, not held-out generalization. The source gate rejected five nonempty proposals in each trial.

Each OCR subprocess has OMP_THREAD_LIMIT=1 and a bounded wall timeout. The first Linux test run passed but took substantially longer than the laptop; a later run failed to obtain an OCR result within the HTTP test readiness window. The actual failing CI output is retained in caught-ci-ocr-readiness.log. Native thread capping prevents concurrent workers from each expanding an OpenMP pool; retained value-free HTTP worker logs and state/queue diagnostics make future failures inspectable. The old run did not retain its temporary worker log, so native oversubscription is a working explanation, not a proven root cause of that particular failure.
