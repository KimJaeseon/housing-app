"""Validate one visually reviewed income/renewal transcription; never evaluate tenants."""
import hashlib
import json
from pathlib import Path

from backend.document_review import load_review, validate_pdf

CURATED_DATA_SHA256 = '335a1b8f9e269e163a8a764e733001d81962c25166daa6585c36717fb654f615'
PERCENTAGES = [30, 50, 70, 100, 110, 120, 130, 150, 160, 170, 180, 190, 200]


def load_reviewed_tables(path, pdf_path, review_path):
    """Bind the partial table record to the reviewed PDF and a visual-review digest.

    The digest detects a changed transcription; updating it requires renewed PDF
    visual review. This check alone does not establish legal applicability.
    """
    validate_pdf(review_path, pdf_path)
    review = load_review(review_path)
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(record) != {'schema_version', 'official_id', 'source_pdf_sha256',
                       'reviewed_at', 'review_method', 'coverage',
                       'applicant_evaluation', 'income_amounts', 'renewal'}:
        raise ValueError('invalid reviewed table fields')
    if (record['schema_version'] != '0.1.0' or record['coverage'] != 'partial'
            or record['applicant_evaluation'] is not False
            or record['official_id'] != review['official_id']
            or record['source_pdf_sha256'] != review['source']['pdf_sha256']
            or record['reviewed_at'] != '2026-10-12'
            or record['review_method'] != 'pdf_text_table_extraction_and_visual_page_review'):
        raise ValueError('reviewed table source mismatch')
    values = {'income_amounts': record['income_amounts'], 'renewal': record['renewal']}
    digest = hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True,
                                       separators=(',', ':')).encode('utf-8')).hexdigest()
    if digest != CURATED_DATA_SHA256:
        raise ValueError('reviewed table transcription changed')
    income = record['income_amounts']
    if income['page'] != 14 or income['unit'] != 'won_per_month' or income['year'] != 2026:
        raise ValueError('income table scope mismatch')
    if (income['threshold_percent'] != PERCENTAGES
            or income['household_sizes'] != list(range(1, 9))
            or len(income['amounts_won']) != 8
            or any(len(row) != 13 or any(type(value) is not int or value <= 0 for value in row)
                   or any(left >= right for left, right in zip(row, row[1:]))
                   for row in income['amounts_won'])
            or income['over_eight_increment_at_100_percent_won'] != 959198):
        raise ValueError('income table shape mismatch')
    renewal = record['renewal']
    if renewal['pages'] != [28, 29, 30, 31] or renewal['scope'] != 'renewal_only':
        raise ValueError('renewal scope mismatch')
    if (renewal['base']['income_band_coefficients_percent'] != [35, 40, 50, 65, 80, 90]
            or renewal['base']['maximum_increase_percent'] != 5
            or renewal['overlap']['rule'] != 'highest_rate_only'):
        raise ValueError('renewal rule mismatch')
    return record
