"""CPU-only PDF fingerprints and query/document/content overlap measurement."""
from collections import defaultdict
from contextlib import closing
import hashlib
from pathlib import Path

from qpaf.m13.corpus import inspect_pdf_directory
from qpaf.m13.splits import read_split_bundle
from qpaf.m13.vidoseek import parse_vidoseek_annotations, format_page_id, page_to_document_id


def load_real_corpus(corpus_dir, annotations, splits_dir):
    import pypdfium2 as pdfium

    inventory = inspect_pdf_directory(corpus_dir)
    parsed = parse_vidoseek_annotations(annotations, inventory['doc_page_counts'])
    query_ids = [q['query_id'] for q in parsed.queries]
    if not query_ids:
        raise ValueError('No queries to audit')
    splits = read_split_bundle(splits_dir, query_ids)
    query_split = {qid: name for name, ids in splits.items() for qid in ids}
    document_splits = defaultdict(set)
    for qid, targets in parsed.qrels.items():
        for target in targets:
            document_splits[page_to_document_id(target)].add(query_split[qid])

    pages, aliases = [], []
    for record in inventory['documents']:
        pdf_path = Path(record['source_path'])
        doc_id = record['document_id']
        memberships = sorted(document_splits[doc_id])
        # Shared retrieval corpus is distinct from query partitions.
        split = memberships[0] if len(memberships) == 1 else ('shared' if memberships else 'unassigned')
        with closing(pdfium.PdfDocument(pdf_path)) as document:
            for index in range(len(document)):
                with closing(document[index]) as page:
                    with closing(page.render(scale=1)) as bitmap:
                        image = bitmap.to_pil().convert('RGB')
                        try:
                            payload = f'pdfium-rgb-72dpi:{image.width}:{image.height}:'.encode() + image.tobytes()
                        finally:
                            image.close()
                page_id = format_page_id(pdf_path.name, index + 1)
                pages.append({'document_id':doc_id, 'page_id':page_id, 'page_number':index+1,
                              'source_path':str(pdf_path), 'file_sha256':record['file_sha256'],
                              'content_sha256':hashlib.sha256(payload).hexdigest(), 'split':split,
                              'extraction_method':'pdfium_rgb_72dpi_v1', 'review_status':'pending_review'})
                aliases.append((f'{doc_id}_{index+1}', f'{pdf_path.name}#page={index+1}'))
        print(f'[PDF] {pdf_path.name}: {record["page_count"]} pages', flush=True)

    content_splits = defaultdict(set)
    content_pages = defaultdict(list)
    for page in pages:
        fingerprint = page['content_sha256']
        content_splits[fingerprint].update(document_splits[page['document_id']])
        content_pages[fingerprint].append(page['page_id'])
    file_groups = defaultdict(list)
    for record in inventory['documents']:
        file_groups[record['file_sha256']].append(record['document_id'])
    overlap = {
        'policy':'query_disjoint_shared_retrieval_corpus; document/content overlap requires independent review',
        'query_overlap_count':0,
        'query_count':len(query_ids),
        'split_counts':{name:len(ids) for name,ids in splits.items()},
        'document_memberships':{doc:sorted(names) for doc,names in sorted(document_splits.items())},
        'overlapping_documents':{doc:sorted(names) for doc,names in sorted(document_splits.items()) if len(names)>1},
        'overlapping_content':[
            {'content_sha256':key, 'splits':sorted(names), 'page_ids':content_pages[key]}
            for key,names in sorted(content_splits.items()) if len(names)>1],
        'duplicate_files':{key:docs for key,docs in sorted(file_groups.items()) if len(docs)>1},
        'semantic_query_equivalence':'not_measured; translations/paraphrases require independent grouping review',
    }
    texts = defaultdict(list)
    for query in parsed.queries:
        texts[' '.join(query['text'].casefold().split())].append(query['query_id'])
    overlap['exact_normalized_query_groups'] = [ids for ids in texts.values() if len(ids)>1]
    overlap['cross_split_exact_query_groups'] = [ids for ids in texts.values()
        if len({query_split[qid] for qid in ids}) > 1]
    return pages, {}, aliases, parsed.qrels, inventory, overlap
