# Docket follow-up drill

1. Where does fixture truth enter extraction? It does not: `ocr` takes only a path. Truth is used by evaluation and explicitly scripted correction helpers.
2. Why keep word offsets and boxes? Text offsets identify the cited OCR span; boxes let the reviewer inspect the corresponding input pixels.
3. Can a source-valid amount still be wrong? Yes. OCR can misread a glyph; internal source support is not image truth.
4. What defeats a moved citation? Qualified label context, exact offsets/value and uniqueness, not substring presence alone.
5. How do negation controls work? Only a complete exact source sentence supports a claim; dropping the leading negation or changing a number fails.
6. Why no semantic entailment claim? Exact matching cannot judge paraphrases, clinical context or whether the original statement is true.
7. Why pin a reviewer revision? Polling must not let an old draft silently overwrite a newer decision. Save uses its original expected revision.
8. Can missing OCR be corrected? Yes, with explicit source-image attestation and a note hash; the evidence kind changes, original OCR does not.
9. Does attestation guarantee a correct human? No. It records responsibility/judgment; independent human accuracy remains unmeasured.
10. How can a dead worker lose publication rights? Its lease expires or a later owner changes the token; completion checks both under the database lock.
11. What did the row-lock regression show? A transaction began before expiry and acquired its lock afterward. Transaction-start now incorrectly allowed publication; a current post-lock clock fixes it.
12. What happens to exhausted abandoned jobs? They become explicit errors rather than remain running forever or silently succeed.
13. Is the model a hidden heuristic? No, actual greedy local generation is recorded. Parser/source gates are separate and cannot count rejected output as success.
14. How is the model cache trusted? Pinned public revision, recorded file hashes and safetensors LFS weight verification; no remote model code execution.
15. What does a schema-valid model output establish? Only the expected string-key shape. Field accuracy and source support are separately measured.
16. How is a commit-before-timeout tested? The mock persists its unique claim, sleeps longer than the real client's timeout, then the outbox retries/reconciles over HTTP.
17. Can an amount change under the same payer key? It is rejected as an idempotency conflict. A production amendment protocol is not implemented.
18. Do view redactions make all logging safe? No. Redaction is a finite tested aid; operational paths instead exclude source/values and emit generic errors. No universal PHI guarantee.
19. Does a restart preserve everything? The tested process/container restart preserves Postgres plus retained source files. Recreating containers requires source/database volumes; ephemeral free storage is insufficient.
20. What is still partial? Independent human review benefit, held-out/general-document validation and production identity/storage/deployment. The measured scripted path is not substituted for those claims.
