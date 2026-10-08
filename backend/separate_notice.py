"""Capture a bounded official LH bulletin snapshot, without inheriting notice facts."""
import hashlib
import json
import re
from html import escape
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener

from jsonschema import Draft202012Validator, FormatChecker
from backend.lh_document import Tree, compact
from backend.lh_probe import NoRedirect

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'shared/contracts/separate-notice.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
Draft202012Validator.check_schema(SCHEMA)
MAX_HTML = 1024 * 1024
MAX_PDF = 10 * 1024 * 1024


def bulletin_id(url):
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if (parts.scheme != 'https' or parts.netloc != 'apply.lh.or.kr' or parts.fragment
            or parts.path != '/lhapply/apply/noti/an/view.do'
            or set(query) != {'bbsSn', 'ccrCnntSysDsCd', 'mi'}
            or any(len(v) != 1 for v in query.values())
            or query['ccrCnntSysDsCd'] != ['03'] or query['mi'] != ['1079']
            or not re.fullmatch(r'[0-9]{1,16}', query['bbsSn'][0])):
        raise ValueError('SEPARATE_NOTICE_URL_INVALID')
    return query['bbsSn'][0]


def parse_page(body, url, expected_title):
    ident = bulletin_id(url)
    text = body.decode('utf-8')
    # Match literal metadata only, never evaluate site JavaScript.
    identities = set(re.findall(r"'\?bbsSn='\s*\+\s*'([0-9]+)'", text))
    if identities != {ident}:
        raise ValueError('SEPARATE_NOTICE_ID_MISMATCH')
    tree = Tree(); tree.feed(text)
    containers = [n for n in tree.root.all('div') if 'bbs_ViewA' in n.attrs.get('class', '').split()]
    if len(containers) != 1:
        raise ValueError('SEPARATE_NOTICE_PAGE_INVALID')
    container = containers[0]
    titles = container.all('h3')
    if len(titles) != 1 or compact(titles[0].text()) != compact(expected_title):
        raise ValueError('SEPARATE_NOTICE_TITLE_MISMATCH')
    dates = []
    for li in container.all('li'):
        strong = li.all('strong')
        if len(strong) == 1 and strong[0].text() == '게시일':
            value = li.text().removeprefix('게시일').strip()
            date.fromisoformat(value); dates.append(value)
    content = [n for n in container.all('div') if 'bbsV_cont' in n.attrs.get('class', '').split()]
    files = []
    groups = [n for n in container.all('div') if 'bbsV_atchmnfl' in n.attrs.get('class', '').split()]
    if len(dates) != 1 or len(content) != 1 or len(groups) != 1:
        raise ValueError('SEPARATE_NOTICE_PAGE_INVALID')
    for a in groups[0].all('a'):
        match = re.fullmatch(r'/lhapply/lhFile.do\?fileid=([0-9]{1,16})', a.attrs.get('href', ''))
        if not match or not a.text().lower().endswith('.pdf'):
            raise ValueError('SEPARATE_NOTICE_ATTACHMENT_UNSUPPORTED')
        files.append({'file_id': match[1], 'filename': a.text(),
                      'url': 'https://apply.lh.or.kr' + a.attrs['href']})
    if not 1 <= len(files) <= 5 or len({f['file_id'] for f in files}) != len(files):
        raise ValueError('SEPARATE_NOTICE_ATTACHMENTS_INVALID')
    return {'bulletin_id': ident, 'title': titles[0].text(), 'published_on': dates[0],
            'summary': ' '.join(content[0].text().split()), 'attachments': files}


def public_extract(body, url, expected_title):
    """Retain bulletin content only; omit page forms, CSRF values and navigation."""
    parsed = parse_page(body, url, expected_title)
    tree = Tree(); tree.feed(body.decode('utf-8'))
    container = next(n for n in tree.root.all('div') if 'bbs_ViewA' in n.attrs.get('class', '').split())
    def serialize(node):
        if isinstance(node, str):
            return escape(' '.join(node.split()))
        if node.tag in ('input', 'script', 'style', 'form'):
            return ''
        attrs = ''.join(' ' + escape(k) + '="' + escape(v or '', quote=True) + '"'
                        for k, v in node.attrs.items() if k in ('class', 'href'))
        return '<' + node.tag + attrs + '>' + ''.join(serialize(c) for c in node.children) + '</' + node.tag + '>'
    metadata = "<!-- Public content extract; literal source identity: '?bbsSn=' + '" + parsed['bulletin_id'] + "' -->\n"
    return (metadata + serialize(container)).encode('utf-8')


def capture(url, expected_title, candidate_official_id, opener=None):
    """Return manifest and bytes; the caller explicitly chooses storage locations."""
    bulletin_id(url)  # Validate before any network request.
    if not re.fullmatch(r'[0-9]{1,32}', candidate_official_id):
        raise ValueError('SEPARATE_NOTICE_CANDIDATE_INVALID')
    client = opener or build_opener(NoRedirect())
    def read(address, limit):
        with client.open(Request(address, headers={'Accept': 'text/html,application/pdf'}), timeout=10) as response:
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('SEPARATE_NOTICE_TOO_LARGE')
        return body
    response_html = read(url, MAX_HTML)
    parsed = parse_page(response_html, url, expected_title)
    html = public_extract(response_html, url, expected_title)
    html_name = 'lh-bulletin-' + parsed['bulletin_id'] + '.html'
    artifacts = {html_name: html}
    for item in parsed['attachments']:
        pdf = read(item['url'], MAX_PDF)
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('SEPARATE_NOTICE_NOT_PDF')
        name = 'lh-bulletin-' + parsed['bulletin_id'] + '-' + item['file_id'] + '.pdf'
        artifacts[name] = pdf
        item.update(artifact=name, sha256=hashlib.sha256(pdf).hexdigest())
    record = dict(schema_version='0.1.0', coverage='partial', relation='candidate',
                  html_scope='public_extract', response_html_sha256=hashlib.sha256(response_html).hexdigest(),
                  candidate_official_id=candidate_official_id, source_url=url,
                  checked_at=datetime.now(timezone.utc).isoformat(),
                  html_artifact=html_name, html_sha256=hashlib.sha256(html).hexdigest(), **parsed)
    if list(VALIDATOR.iter_errors(record)):
        raise ValueError('SEPARATE_NOTICE_RECORD_INVALID')
    return record, artifacts


def load_snapshot(record_path, artifact_dir, official_id):
    """Bind manifest to stored HTML and every attachment; never assert completeness."""
    record = json.loads(Path(record_path).read_text(encoding='utf-8'))
    if list(VALIDATOR.iter_errors(record)) or record['candidate_official_id'] != official_id:
        raise ValueError('SEPARATE_NOTICE_RECORD_INVALID')
    directory = Path(artifact_dir).resolve()
    if record['html_artifact'] != 'lh-bulletin-' + record['bulletin_id'] + '.html':
        raise ValueError('SEPARATE_NOTICE_ARTIFACT_INVALID')
    def read_artifact(name, digest, limit):
        path = (directory / name).resolve()
        if path.parent != directory or path.stat().st_size > limit:
            raise ValueError('SEPARATE_NOTICE_ARTIFACT_INVALID')
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError('SEPARATE_NOTICE_ARTIFACT_CHANGED')
        return body
    html = read_artifact(record['html_artifact'], record['html_sha256'], MAX_HTML)
    parsed = parse_page(html, record['source_url'], record['title'])
    for key in ('bulletin_id', 'title', 'published_on', 'summary'):
        if parsed[key] != record[key]:
            raise ValueError('SEPARATE_NOTICE_METADATA_CHANGED')
    observed = [{k: a[k] for k in ('file_id', 'filename', 'url')} for a in record['attachments']]
    if observed != parsed['attachments']:
        raise ValueError('SEPARATE_NOTICE_ATTACHMENTS_CHANGED')
    for a in record['attachments']:
        if a['artifact'] != 'lh-bulletin-' + record['bulletin_id'] + '-' + a['file_id'] + '.pdf':
            raise ValueError('SEPARATE_NOTICE_ARTIFACT_INVALID')
        if not read_artifact(a['artifact'], a['sha256'], MAX_PDF).startswith(b'%PDF-'):
            raise ValueError('SEPARATE_NOTICE_NOT_PDF')
    return record
