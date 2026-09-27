"""Frozen scorers and aligned score caches. No scorer accepts qrels."""
from collections import Counter
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


def dense_scores(queries, texts, config, output, logger, cache_dir):
    import numpy as np
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(config['model_id'], revision=config['revision'],
                                device=config['device'], cache_folder=str(cache_dir), trust_remote_code=False)
    model.max_seq_length = config['max_seq_length']
    model.eval()
    model.requires_grad_(False)
    logger.info('dense model loaded: %s at %s', config['model_id'], config['revision'])
    common = {'batch_size': config['batch_size'], 'normalize_embeddings': True,
              'convert_to_numpy': True, 'show_progress_bar': True}
    query_vectors = model.encode([config['query_prefix']+query for query in queries], **common)
    page_vectors = model.encode([config['page_prefix']+text for text in texts], **common)
    np.save(output/'query_embeddings.npy', query_vectors, allow_pickle=False)
    np.save(output/'page_embeddings.npy', page_vectors, allow_pickle=False)
    logger.info('dense encoded %d queries and %d pages', len(queries), len(texts))
    return query_vectors @ page_vectors.T


def visual_scores(queries, pages, prepared, config, output, logger, cache_dir):
    import numpy as np
    import torch
    from PIL import Image
    from colpali_engine.models import ColQwen2, ColQwen2Processor
    from peft import PeftModel

    dtype = getattr(torch, config['dtype'])
    # Pin base weights separately: pinning only the LoRA repo leaves the base mutable.
    model = ColQwen2.from_pretrained(config['base_model_id'], revision=config['base_revision'],
               torch_dtype=dtype, device_map=config['device'], cache_dir=str(cache_dir),
               attn_implementation=config['attention'])
    model = PeftModel.from_pretrained(model, config['model_id'], revision=config['revision'],
                                     cache_dir=str(cache_dir), is_trainable=False).eval()
    model.requires_grad_(False)
    processor = ColQwen2Processor.from_pretrained(config['model_id'], revision=config['revision'],
                                                 cache_dir=str(cache_dir))
    processor.query_prefix = config['query_prefix']
    processor.image_processor.max_pixels = config['max_pixels']
    processor.image_processor.size['longest_edge'] = config['max_pixels']
    logger.info('visual adapter and base loaded; device=%s dtype=%s', config['device'], config['dtype'])
    index = output/'embeddings'
    index.mkdir()
    query_vectors = []
    with torch.inference_mode():
        for start in range(0, len(queries), config['query_batch_size']):
            batch = processor.process_queries(queries[start:start+config['query_batch_size']]).to(model.device)
            query_vectors.extend(embedding.cpu() for embedding in model(**batch))
        torch.save(query_vectors, index/'queries.pt')
        result = np.zeros((len(queries), len(pages)), dtype=np.float32)
        for shard_start in range(0, len(pages), config['embedding_shard_size']):
            shard = pages[shard_start:shard_start+config['embedding_shard_size']]
            vectors = []
            for start in range(0, len(shard), config['batch_size']):
                images = []
                try:
                    for row in shard[start:start+config['batch_size']]:
                        with Image.open(prepared/row['image']) as original:
                            images.append(original.convert('RGB'))
                    batch = processor.process_images(images).to(model.device)
                    vectors.extend(embedding.cpu() for embedding in model(**batch))
                finally:
                    for image in images:
                        image.close()
            torch.save(vectors, index/f'pages-{shard_start:08d}.pt')
            values = processor.score_multi_vector(query_vectors, vectors, batch_size=config['score_batch_size'],
                                                   device=config['device'])
            result[:, shard_start:shard_start+len(shard)] = values.float().cpu().numpy()
            logger.info('visual scored %d / %d pages for %d queries', shard_start+len(shard), len(pages), len(queries))
    return result
