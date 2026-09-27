"""Original ViDoSeek adapter. Labels and answers are separated from scoring inputs."""
import hashlib
from contextlib import closing
from pathlib import Path
import stat
import zipfile

from .artifacts import digest, read_json, write_csv, write_json
from .config import relative_path


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
    pages, document_pages, seen = [], {}, set()
    counts = {'native': 0, 'ocr': 0, 'empty': 0}
    for pdf in pdfs:
        if pdf.name in document_pages:
            raise ValueError(f'Duplicate corpus filename: {pdf.name}')
        page_ids = []
        with closing(pdfium.PdfDocument(pdf)) as document:
            for index in range(len(document)):
                page_id = f'{pdf.stem}_{index+1}'
                if page_id in seen:
                    raise ValueError(f'Duplicate page ID: {page_id}')
                seen.add(page_id)
                page_ids.append(page_id)
                with closing(document[index]) as page:
                    with closing(page.get_textpage()) as textpage:
                        text = textpage.get_text_bounded().strip()
                    with closing(page.render(scale=config['text']['dpi']/72)) as bitmap:
                        image = bitmap.to_pil().convert('RGB')
                    try:
                        text_source = 'native'
                        mode = config['text']['mode']
                        if mode == 'ocr' or (mode == 'native_or_ocr' and len(text) < config['text']['min_native_chars']):
                            text = pytesseract.image_to_string(image, lang=config['text']['ocr_language'],
                                                               timeout=config['text']['ocr_timeout']).strip()
                            text_source = 'ocr'
                        image_path = image_dir/(page_id+'.png')
                        image.save(image_path)
                    finally:
                        image.close()
                counts[text_source] += 1
                counts['empty'] += int(not text)
                pages.append({'page_id': page_id, 'document': pdf.name, 'page_number': index+1,
                              'text': text, 'text_source': text_source,
                              'image': image_path.relative_to(output).as_posix()})
        document_pages[pdf.name] = page_ids
        logger.info('extracted %s: %d pages; total %d', pdf.name, len(page_ids), len(pages))
    queries, qrels = annotations(read_json(downloads['annotation_file']), dataset['annotation_key'], document_pages)
    selected = select_queries(queries, config['selection']['count'], config['selection']['seed'])
    write_json(output/'pages.json', sorted(pages, key=lambda p: p['page_id']))
    write_csv(output/'page_manifest.csv', [
        {'page_id': page['page_id'], 'document': page['document'], 'page_number': page['page_number'],
         'image': page['image'], 'image_sha256': digest(output/page['image']),
         'text_source': page['text_source'], 'text_sha256': hashlib.sha256(page['text'].encode()).hexdigest()}
        for page in sorted(pages, key=lambda p: p['page_id'])])
    write_json(output/'queries.json', selected)
    write_json(output/'qrels.json', {q['query_id']: qrels[q['query_id']] for q in selected})
    write_json(output/'dataset.json', {'repo_id': dataset['repo_id'], 'revision': dataset['revision'],
               'sources': sources, 'total_queries': len(queries), 'selected_queries': len(selected),
               'total_pages': len(pages), 'total_documents': len(document_pages),
               'page_number_base': 1, 'selection': config['selection'], 'text_extraction_counts': counts})
