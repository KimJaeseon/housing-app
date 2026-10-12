"""Check preserved official legal sources without deciding applicant eligibility."""

import hashlib
import json
from pathlib import Path


SOURCES = {
    'annex_5_2': {
        'file': 'law-public-housing-rule-annex-5-2-2025-10-31.pdf',
        'sha256': '9b405322c5f5cb38872252acad43e89fc2447cccea575a9b53bcc85da96a7e2d',
        'effective_date': None,
        'amended_date': '2025-10-31',
    },
    'rent_standard': {
        'file': 'molit-integrated-public-rent-standard-2024-720.pdf',
        'sha256': 'b21d18ecd88de05298ca69df4e48b5431f007dce188917b38e8e38d1aa3eabb4',
        'effective_date': '2024-12-05',
        'amended_date': '2024-12-05',
    },
}

CHECKS = {
    'annex_general_income': 'aligned',
    'annex_premarital_deadline': 'unresolved',
    'annex_single_parent_fetus': 'unresolved',
    'rent_income_coefficients': 'aligned',
    'rent_deposit_share': 'aligned',
    'rent_surcharges': 'aligned',
}


def load_external_legal(path, artifact_dir, official_id):
    """Verify source bytes and the narrow, manually reviewed comparison record."""
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(record) != {'schema_version', 'official_id', 'notice_date', 'reviewed_at',
                       'coverage', 'applicability_verified', 'applicant_evaluation',
                       'sources', 'checks'}:
        raise ValueError('invalid external legal fields')
    if (record['schema_version'] != '0.1.0'
            or record['official_id'] != official_id
            or record['notice_date'] != '2026-09-17'
            or record['reviewed_at'] != '2026-10-12'
            or record['coverage'] != 'partial'
            or record['applicability_verified'] is not False
            or record['applicant_evaluation'] is not False
            or record['sources'] != SOURCES
            or record['checks'] != CHECKS):
        raise ValueError('external legal record mismatch')
    for source in SOURCES.values():
        candidate = Path(artifact_dir) / source['file']
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('external legal source changed')
    return record
