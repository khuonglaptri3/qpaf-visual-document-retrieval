"""Original ViDoSeek adapter. Labels and answers are separated from scoring inputs."""
import hashlib
import importlib.metadata
import math
from contextlib import closing
from pathlib import Path
import stat
import zipfile

from .artifacts import digest, read_json, write_csv, write_json
from .config import relative_path
from qpaf.m13.vidoseek import format_page_id
from qpaf.m18.ocr_policy import evaluate_page_text


def select_queries(queries, count, seed):
    if type(count) is not int or count < 0 or count > len(queries):
        raise ValueError('Query count must be zero (all) or <= dataset size')
    ranked = sorted(queries, key=lambda row: (hashlib.sha256(f'{seed}:{row["query_id"]}'.encode()).digest(), row['query_id']))
    chosen = ranked if count == 0 else ranked[:count]
    return sorted(chosen, key=lambda row: row['query_id'])


def annotations(raw, key, document_pages):
    examples = raw[key]
    if not isinstance(examples, list) or not examples:
        raise ValueError('Annotation examples must be a nonempty list')
    queries, qrels = [], {}
    for example in examples:
        query = example['uid']
        text = example['query']
        if not isinstance(query, str) or not query or query in qrels or not isinstance(text, str) or not text.strip():
            raise ValueError('Missing/duplicate query ID or empty query text')
        meta = example['meta_info']
        filename = meta['file_name']
        refs = meta['reference_page']
        if filename not in document_pages or not isinstance(refs, list) or not refs:
            raise ValueError(f'Unknown document or empty reference pages for {query}')
        pages = document_pages[filename]
        labels = {}
        for page in refs:
            if type(page) is not int or page < 1 or page > len(pages):
                raise ValueError(f'Invalid one-based page number for {query}: {page}')
            labels[pages[page-1]] = 1
        queries.append({'query_id': query, 'text': text})
        qrels[query] = labels
    return queries, qrels


def extract_zip(archive, output):
    output = Path(output).resolve()
    with zipfile.ZipFile(archive) as zipped:
        names = set()
        # Validate the whole archive before extracting its first member.
        for info in zipped.infolist():
            name = info.filename.rstrip('/')
            relative = relative_path(name)
            destination = output.joinpath(*relative.parts).resolve()
            canonical = str(destination).casefold()
            if not destination.is_relative_to(output) or canonical in names or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f'Unsafe/duplicate ZIP member: {info.filename}')
            names.add(canonical)
        zipped.extractall(output)


def prepare(config, output, logger, cache_dir):
    import pypdfium2 as pdfium
    import pytesseract
    from huggingface_hub import hf_hub_download

    dataset = config['dataset']
    parser_version = importlib.metadata.version('pypdfium2')
    if parser_version != config['text']['parser_version']:
        raise ValueError(f'PDFium parser version {parser_version} does not match configured {config["text"]["parser_version"]}')
    runtime = {'parser_version': parser_version, 'ocr_engine_version': None}
    sources = {}
    downloads = {}
    for name in ('annotation_file', 'corpus_file'):
        path = Path(hf_hub_download(dataset['repo_id'], dataset[name], repo_type='dataset',
                                   revision=dataset['revision'], cache_dir=str(cache_dir)))
        downloads[name] = path
        sources[dataset[name]] = {'sha256': digest(path), 'size_bytes': path.stat().st_size}
    raw_dir = output/'pdfs'
    extract_zip(downloads['corpus_file'], raw_dir)
    pdfs = sorted(raw_dir.rglob('*.pdf'))
    if not pdfs:
        raise ValueError('Downloaded corpus contains no PDF files')
    image_dir = output/'images'
    image_dir.mkdir()
    pages, document_pages, seen, failures = [], {}, set(), []
    counts = {'native': 0, 'ocr': 0, 'empty': 0, 'failed': 0}
    policy = config['text']
    corrupt_documents = 0
    for pdf in pdfs:
        if pdf.name in document_pages:
            raise ValueError(f'Duplicate corpus filename: {pdf.name}')
        page_ids = []
        try:
            document = pdfium.PdfDocument(pdf)
            if not len(document):
                document.close()
                raise ValueError('PDF has no pages')
        except Exception as exc:
            corrupt_documents += 1
            failures.append({'document': pdf.name, 'page_id': '', 'page_number': '',
                             'reason': 'pdf_open_failed', 'error': f'{type(exc).__name__}: {exc}'})
            logger.error('cannot open %s: %s', pdf.name, exc)
            continue
        with closing(document):
            for index in range(len(document)):
                page_id = format_page_id(pdf.name, index+1)
                if page_id in seen:
                    raise ValueError(f'Duplicate page ID: {page_id}')
                seen.add(page_id)
                page_ids.append(page_id)
                text, text_source, confidence, image_name = '', 'native', None, ''
                status, reason, error = 'EXTRACTION_FAILED', 'page_extraction_failed', ''
                try:
                    with closing(document[index]) as page:
                        # Failed native parsing still permits OCR of a renderable page.
                        try:
                            with closing(page.get_textpage()) as textpage:
                                text = textpage.get_text_bounded().strip()
                        except Exception:
                            text = ''
                        with closing(page.render(scale=policy['dpi']/72)) as bitmap:
                            image = bitmap.to_pil().convert('RGB')
                        try:
                            image_path = image_dir/(page_id+'.png')
                            image.save(image_path)
                            image_name = image_path.relative_to(output).as_posix()
                            decision = evaluate_page_text(text, min_chars=policy['min_native_chars'],
                                                          min_printable_ratio=policy['min_printable_ratio'])
                            if policy['mode'] == 'ocr' or (policy['mode'] == 'native_or_ocr' and decision.route == 'OCR_FALLBACK_TRIGGERED'):
                                text_source = 'ocr'
                                if runtime['ocr_engine_version'] is None:
                                    runtime['ocr_engine_version'] = str(pytesseract.get_tesseract_version())
                                if runtime['ocr_engine_version'] != policy['ocr_engine_version']:
                                    raise ValueError(f'OCR engine version {runtime["ocr_engine_version"]} does not match configured {policy["ocr_engine_version"]}')
                                data = pytesseract.image_to_data(image, lang=policy['ocr_language'],
                                    timeout=policy['ocr_timeout'], output_type=pytesseract.Output.DICT)
                                words = [(str(word).strip(), float(conf)) for word, conf in zip(data['text'], data['conf'])
                                         if str(word).strip()]
                                text = ' '.join(word for word, _ in words)
                                confidences = [conf for _, conf in words if math.isfinite(conf) and 0 <= conf <= 100]
                                confidence = sum(confidences)/len(confidences) if confidences else 0.0
                                decision = evaluate_page_text(text, confidence=confidence,
                                    min_chars=policy['min_ocr_chars'], min_printable_ratio=policy['min_printable_ratio'],
                                    min_confidence=policy['min_ocr_confidence'])
                            status, reason = decision.route, decision.reason
                            if status == 'OCR_FALLBACK_TRIGGERED':
                                status, reason = 'EXTRACTION_FAILED', 'native_quality_failed_ocr_disabled'
                        finally:
                            image.close()
                except Exception as exc:
                    reason = 'ocr_timeout' if text_source == 'ocr' and 'timeout' in str(exc).lower() else 'page_extraction_failed'
                    error = f'{type(exc).__name__}: {exc}'
                if status == 'EXTRACTION_FAILED':
                    counts['failed'] += 1
                    failures.append({'document': pdf.name, 'page_id': page_id, 'page_number': index+1,
                                     'reason': reason, 'error': error})
                counts[text_source] += 1
                counts['empty'] += int(not text)
                pages.append({'page_id': page_id, 'document': pdf.name, 'page_number': index+1,
                              'text': text, 'text_source': text_source, 'ocr_confidence': confidence,
                              'extraction_status': status, 'extraction_reason': reason, 'image': image_name})
        document_pages[pdf.name] = page_ids
        logger.info('extracted %s: %d pages; total %d', pdf.name, len(page_ids), len(pages))
    write_json(output/'pages.json', sorted(pages, key=lambda p: p['page_id']))
    write_csv(output/'failures.csv', failures, fields=['document', 'page_id', 'page_number', 'reason', 'error'])
    fraction = counts['failed']/len(pages) if pages else 1.0
    write_json(output/'extraction_summary.json', {'quality_status': policy['quality_status'],
               'policy': policy, 'runtime': runtime, 'sources': sources,
               'total_pages': len(pages), 'failed_pages': counts['failed'],
               'corrupt_documents': corrupt_documents, 'failure_fraction': fraction,
               'max_failure_fraction': policy['max_failure_fraction']})
    write_csv(output/'page_manifest.csv', [
        {'page_id': page['page_id'], 'document': page['document'], 'page_number': page['page_number'],
         'image': page['image'], 'image_sha256': digest(output/page['image']) if page['image'] else '',
         'extraction_status': page['extraction_status'],
         'text_source': page['text_source'], 'text_sha256': hashlib.sha256(page['text'].encode()).hexdigest()}
        for page in sorted(pages, key=lambda p: p['page_id'])],
        fields=['page_id', 'document', 'page_number', 'image', 'image_sha256', 'extraction_status', 'text_source', 'text_sha256'])
    # This subset remains immutable even when StageRun later records a failure.
    evidence_paths = [output/name for name in ('pages.json', 'failures.csv', 'page_manifest.csv', 'extraction_summary.json')]
    evidence_paths.extend(image_dir.glob('*.png'))
    evidence_paths.extend(pdfs)
    write_json(output/'extraction_hashes.json', [
        {'path': path.relative_to(output).as_posix(), 'size_bytes': path.stat().st_size, 'sha256': digest(path)}
        for path in sorted(evidence_paths)])
    if corrupt_documents:
        raise ValueError('Corrupt/empty PDF documents prevent complete corpus extraction; see failures.csv')
    if fraction > policy['max_failure_fraction']:
        raise ValueError(f'Corpus failure fraction {fraction:.6f} exceeds {policy["max_failure_fraction"]}; see failures.csv')
    queries, qrels = annotations(read_json(downloads['annotation_file']), dataset['annotation_key'], document_pages)
    selected = select_queries(queries, config['selection']['count'], config['selection']['seed'])
    write_json(output/'queries.json', selected)
    write_json(output/'qrels.json', {q['query_id']: qrels[q['query_id']] for q in selected})
    write_json(output/'dataset.json', {'repo_id': dataset['repo_id'], 'revision': dataset['revision'],
               'sources': sources, 'total_queries': len(queries), 'selected_queries': len(selected),
               'total_pages': len(pages), 'total_documents': len(document_pages),
               'page_number_base': 1, 'selection': config['selection'], 'text_extraction_counts': counts})
