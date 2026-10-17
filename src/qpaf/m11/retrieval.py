"""Frozen scorers and aligned score caches. No scorer accepts qrels."""
from collections import Counter
from contextlib import nullcontext
import math
from pathlib import Path
import re

from .artifacts import digest, read_json, write_json


def bm25_scores(queries, texts, k1, b):
    """BM25 with positive Robertson IDF, Unicode word tokens and lowercase."""
    import numpy as np
    tokenized = [Counter(re.findall(r'\w+', text.lower())) for text in texts]
    lengths = np.array([sum(doc.values()) for doc in tokenized], dtype=np.float64)
    average = float(lengths.mean()) if len(lengths) else 0
    output = np.zeros((len(queries), len(texts)), dtype=np.float64)
    if not average:
        return output
    vocabulary = {term for query in queries for term in re.findall(r'\w+', query.lower())}
    term_scores = {}
    for term in vocabulary:
        frequency = np.array([doc[term] for doc in tokenized], dtype=np.float64)
        df = int((frequency > 0).sum())
        idf = math.log1p((len(texts)-df+.5)/(df+.5))
        denominator = frequency+k1*(1-b+b*lengths/average)
        term_scores[term] = np.divide(idf*frequency*(k1+1), denominator,
                                     out=np.zeros_like(frequency), where=denominator != 0)
    for qi, query in enumerate(queries):
        for term in re.findall(r'\w+', query.lower()):
            output[qi] += term_scores[term]
    return output


def save_score_cache(output, scores, query_ids, page_ids, channel):
    import numpy as np
    array = np.asarray(scores)
    if array.shape != (len(query_ids), len(page_ids)) or not np.isfinite(array).all():
        raise ValueError('Score matrix has wrong shape or nonfinite values')
    if not query_ids or not page_ids or len(set(query_ids)) != len(query_ids) or len(set(page_ids)) != len(page_ids):
        raise ValueError('Cache IDs must be nonempty and unique')
    np.save(output/'scores.npy', array, allow_pickle=False)
    write_json(output/'scores.json', {'channel': channel, 'query_ids': query_ids, 'page_ids': page_ids,
               'shape': list(array.shape), 'dtype': str(array.dtype), 'sha256': digest(output/'scores.npy')})


def load_score_cache(folder, query_ids, page_ids, channel):
    import numpy as np
    meta = read_json(folder/'scores.json')
    if meta['query_ids'] != query_ids or meta['page_ids'] != page_ids or meta['channel'] != channel:
        raise ValueError('Score cache IDs/order/channel do not match dataset')
    if digest(folder/'scores.npy') != meta['sha256']:
        raise ValueError('Score cache checksum mismatch')
    scores = np.load(folder/'scores.npy', allow_pickle=False)
    if scores.shape != (len(query_ids), len(page_ids)) or not np.isfinite(scores).all():
        raise ValueError('Score cache is incomplete or nonfinite')
    return scores


def _phase(observer, name):
    return observer(name) if observer is not None else nullcontext()


def dense_scores(queries, texts, config, output, logger, cache_dir, *, observer=None, reference_output=None):
    import numpy as np
    from sentence_transformers import SentenceTransformer
    with _phase(observer, 'load_model'):
        model = SentenceTransformer(config['model_id'], revision=config['revision'],
                                    device=config['device'], cache_folder=str(cache_dir), trust_remote_code=False)
    model.max_seq_length = config['max_seq_length']
    model.eval()
    model.requires_grad_(False)
    logger.info('dense model loaded: %s at %s', config['model_id'], config['revision'])
    common = {'batch_size': config['batch_size'], 'normalize_embeddings': True,
              'convert_to_numpy': True, 'show_progress_bar': True}
    with _phase(observer, 'encode_queries'):
        query_vectors = model.encode([config['query_prefix']+query for query in queries], **common)
    with _phase(observer, 'encode_pages'):
        page_vectors = model.encode([config['page_prefix']+text for text in texts], **common)
    np.save(output/'query_embeddings.npy', query_vectors, allow_pickle=False)
    np.save(output/'page_embeddings.npy', page_vectors, allow_pickle=False)
    logger.info('dense encoded %d queries and %d pages', len(queries), len(texts))
    with _phase(observer, 'score'):
        scores = query_vectors @ page_vectors.T
    if reference_output is not None:
        reference_output.mkdir()
        common['batch_size'] = 1
        with _phase(observer, 'reference_encode'):
            ref_queries = model.encode([config['query_prefix']+query for query in queries], **common)
            ref_pages = model.encode([config['page_prefix']+text for text in texts], **common)
        np.save(reference_output/'query_embeddings.npy', ref_queries, allow_pickle=False)
        np.save(reference_output/'page_embeddings.npy', ref_pages, allow_pickle=False)
        np.save(reference_output/'scores.npy', ref_queries @ ref_pages.T, allow_pickle=False)
    return scores


def visual_scores(queries, pages, prepared, config, output, logger, cache_dir, *, observer=None, reference_output=None):
    import numpy as np
    import torch
    from PIL import Image
    if config.get('family', 'colqwen2') == 'colqwen2_5':
        from colpali_engine.models import ColQwen2_5 as Model, ColQwen2_5_Processor as Processor
    else:
        from colpali_engine.models import ColQwen2 as Model, ColQwen2Processor as Processor
    from peft import PeftModel

    dtype = getattr(torch, config['dtype'])
    # Pin base weights separately: pinning only the LoRA repo leaves the base mutable.
    with _phase(observer, 'load_model'):
        model = Model.from_pretrained(config['base_model_id'], revision=config['base_revision'],
                   torch_dtype=dtype, device_map=config['device'], cache_dir=str(cache_dir),
                   attn_implementation=config['attention'])
        model = PeftModel.from_pretrained(model, config['model_id'], revision=config['revision'],
                                         cache_dir=str(cache_dir), is_trainable=False).eval()
    model.requires_grad_(False)
    processor_id = config.get('processor_id', config['model_id'])
    processor_revision = config.get('processor_revision', config['revision'])
    processor_options = {'revision': processor_revision, 'cache_dir': str(cache_dir)}
    if config.get('processor_local_snapshot'):
        from huggingface_hub import snapshot_download
        # Older Transformers lists new Hub chat templates under an incompatible path.
        # Resolve the exact downloaded snapshot instead; never fall back to main.
        processor_id = snapshot_download(processor_id, revision=processor_revision,
                                         cache_dir=str(cache_dir), local_files_only=True)
        processor_options['local_files_only'] = True
        processor_options['use_fast'] = config['processor_use_fast']
    with _phase(observer, 'load_processor'):
        processor = Processor.from_pretrained(processor_id, **processor_options)
    processor.query_prefix = config['query_prefix']
    processor.image_processor.max_pixels = config['max_pixels']
    processor.image_processor.size['longest_edge'] = config['max_pixels']
    if 'min_pixels' in config:
        processor.image_processor.min_pixels = config['min_pixels']
        processor.image_processor.size['shortest_edge'] = config['min_pixels']
    logger.info('visual adapter and base loaded; device=%s dtype=%s', config['device'], config['dtype'])
    def encode_and_score(destination, query_batch, page_batch, score_batch, prefix=''):
        index = destination/'embeddings'
        index.mkdir(parents=True)
        query_vectors = []
        with torch.inference_mode():
            with _phase(observer, prefix+'encode_queries'):
                for start in range(0, len(queries), query_batch):
                    batch = processor.process_queries(queries[start:start+query_batch]).to(model.device)
                    if batch['input_ids'].shape[1] > config.get('max_query_tokens', 1000000):
                        raise ValueError('Visual query exceeds configured token cap')
                    query_vectors.extend(embedding.cpu() for embedding in model(**batch))
            torch.save(query_vectors, index/'queries.pt')
            result = np.zeros((len(queries), len(pages)), dtype=np.float32)
            for shard_start in range(0, len(pages), config['embedding_shard_size']):
                shard = pages[shard_start:shard_start+config['embedding_shard_size']]
                vectors = []
                with _phase(observer, prefix+'encode_pages'):
                    for start in range(0, len(shard), page_batch):
                        images = []
                        try:
                            for row in shard[start:start+page_batch]:
                                with Image.open(prepared/row['image']) as original:
                                    images.append(original.convert('RGB'))
                            batch = processor.process_images(images).to(model.device)
                            vectors.extend(embedding.cpu() for embedding in model(**batch))
                        finally:
                            for image in images:
                                image.close()
                torch.save(vectors, index/f'pages-{shard_start:08d}.pt')
                with _phase(observer, prefix+'score'):
                    values = processor.score_multi_vector(query_vectors, vectors, batch_size=score_batch,
                                                           device=config['device'])
                    result[:, shard_start:shard_start+len(shard)] = values.float().cpu().numpy()
                logger.info('visual scored %d / %d pages for %d queries', shard_start+len(shard), len(pages), len(queries))
        return result

    scores = encode_and_score(output, config['query_batch_size'], config['batch_size'], config['score_batch_size'])
    if reference_output is not None:
        reference = encode_and_score(reference_output, 1, 1, 1, 'reference_')
        np.save(reference_output/'scores.npy', reference, allow_pickle=False)
    return scores
