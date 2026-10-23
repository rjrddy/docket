# Docket actual measurements

synthetic rendered PNGs, actual Tesseract OCR; confidence is uncalibrated; scripted truth-assisted review, NOT independent human review

tesseract 5.5.0; OCR campaign 8.403 seconds including rendering/database work; not service throughput.

| Template | n | document_id | date | amount | entity | reference | zone | domain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| invoice-a | 6 | 83.33% | 100.00% | 83.33% | 100.00% | 83.33% | 33.33% | 50.00% |
| invoice-b | 6 | 83.33% | 100.00% | 100.00% | 100.00% | 83.33% | 33.33% | 50.00% |
| referral-a | 6 | 83.33% | 100.00% | 83.33% | 100.00% | 66.67% | 100.00% | 50.00% |
| referral-b | 6 | 100.00% | 83.33% | 83.33% | 83.33% | 83.33% | 100.00% | 33.33% |
| statement-a | 6 | 83.33% | 100.00% | 100.00% | 100.00% | 83.33% | 100.00% | 33.33% |
| statement-b | 6 | 83.33% | 100.00% | 100.00% | 100.00% | 83.33% | 100.00% | 50.00% |

## Automation/error curve

| Threshold | Auto count | Auto rate | Auto error rate |
|---|---:|---:|---:|
| 0 | 11 | 30.56% | 0.00% |
| 0.5 | 8 | 22.22% | 0.00% |
| 0.8 | 4 | 11.11% | 0.00% |
| 0.9 | 0 | 0.00% | not measured: no auto cases |
| 0.93 | 0 | 0.00% | not measured: no auto cases |
| 0.95 | 0 | 0.00% | not measured: no auto cases |
| 0.99 | 0 | 0.00% | not measured: no auto cases |

## Review scope

46/56 → 56/56 correct fields via truth-assisted scripted corrections on 8 selected erroneous cases. This proves the persisted correction path, not an independent human effect. Human accuracy/time benefit: not measured.

## Entity matching

144 synthetic pairs; pipeline top-one 97.22% before review. Scores are similarities, not probabilities.

| Threshold | Precision | Recall | TP / FP / FN |
|---|---:|---:|---|
| 0.5 | 11.54% | 100.00% | 12 / 92 / 0 |
| 0.7 | 40.00% | 100.00% | 12 / 18 / 0 |
| 0.8 | 100.00% | 75.00% | 9 / 0 / 3 |
| 0.9 | 100.00% | 75.00% | 9 / 0 / 3 |
| 0.95 | 100.00% | 75.00% | 9 / 0 / 3 |
| 0.99 | 100.00% | 50.00% | 6 / 0 / 6 |

## Negative controls

Raw-content logging rejected; 0 leaks across 5 fixed redaction sentinels. Number/negation/empty claim controls are retained. These finite controls are not a clinical entailment evaluation or general privacy certification.

[All OCR, independent fixture truth, source spans and review rows](evaluation.json). [Model raw generation and schema/source outcomes](model-evaluation.json). [Earlier smaller-model rejection](rejected-smollm-evaluation.json). Confidence is uncalibrated. In-sample empirical zero errors on a small accepted subset does not establish a production error bound.
