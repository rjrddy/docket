# Confidence is not correctness

Tesseract words retain offsets and image boxes. A field needs a unique, complete labeled OCR span; missing/ambiguous values route to review. Confidence is the minimum word confidence in that field, not a calibrated correctness probability. The default conservative route threshold is fixed before evaluation and remains unchanged even when it routes every measured document to review.

Citation verification checks the value, offsets AND field-label context. Whole-sentence claim matching rejects changed numbers, negation substrings and unsupported paraphrases. It is not semantic/clinical entailment. OCR itself may be wrong even when its own span supports the extraction.

A reviewer can attest to the immutable synthetic source image to correct a missing/wrong OCR value. That is a separate evidence class, not manufactured OCR support. Original OCR stays intact, note/value hashes avoid copying content into audit events, and optimistic revisions prevent concurrent overwrites.

The truth-assisted benchmark exercises this persisted path, but is not a human reviewer study. Human accuracy and time saved remain not measured.

The optional model is a development-set experiment, not a calibrated confidence source. Qwen produced 18/42 correct fields on the fixed six-document subset. Adding explicit template-label hints reduced that to 11/42, so the simpler prompt was restored and rerun. Both raw trials are retained; this comparison is development tuning, not held-out generalization. The source gate rejected five nonempty proposals in each trial.
