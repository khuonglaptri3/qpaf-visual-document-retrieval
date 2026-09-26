"""Verify the local method core and retain software-only evidence in a new directory."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m11.artifacts import StageRun, digest, object_hash, source_provenance, write_csv, write_json
from qpaf.m12.config import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.output.exists():
        raise FileExistsError('Output already exists; choose a new verification directory')
    import torch
    from qpaf.m12.features import FEATURE_NAMES, build_features
    from qpaf.m12.losses import pairwise_logistic_loss
    from qpaf.m12.model import make_model

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    fixture = {
        'kind': 'synthetic_software_verification',
        'query_texts': ['apple pear', 'quarterly sales chart'],
        'page_ids': [['c', 'a', 'b'], ['x', 'y', '']],
        'raw_scores': [[[4., 20., 7.], [2., 10., 7.], [0., 30., 7.]],
                       [[0., 5., 2.], [3., 0., 2.], [0., 0., 0.]]],
        'mask': [[True, True, True], [True, True, False]],
        'labels_for_loss_only': [[1., 0., 0.], [1., 0., -1.]],
    }
    source = source_provenance(ROOT, 'requirements/m12-cpu.txt')
    paths = [*sorted((ROOT/'tests').glob('test_m12*.py')),
             ROOT/'docs/m1.2-method-core.md', args.config.resolve()]
    source['method_inputs'] = [{'path': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT)
                               else str(path), 'sha256': digest(path)} for path in paths]
    source['digest'] = object_hash({'implementation': source['digest'], 'method_inputs': source['method_inputs']})
    inputs = {'config': digest(args.config), 'fixture': object_hash(fixture)}
    with StageRun(args.output, 'verification', config, inputs, source) as run:
        write_json(run.path/'fixture.json', fixture)
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        # Exclude the CLI integration test to avoid recursively invoking this script.
        for pattern in ('test_m12_config.py', 'test_m12_core.py'):
            suite.addTests(loader.discover(str(ROOT/'tests'), pattern=pattern))
        with (run.path/'unit-tests.log').open('w', encoding='utf-8') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        tests = {'run': result.testsRun, 'failures': len(result.failures),
                 'errors': len(result.errors), 'skipped': len(result.skipped)}
        write_json(run.path/'unit-tests.json', tests)
        if not result.wasSuccessful() or not result.testsRun or result.skipped:
            raise RuntimeError('Method-core tests must pass without skips; inspect unit-tests.log')
        run.logger.info('method-core unit tests passed: %d', result.testsRun)

        raw = torch.tensor(fixture['raw_scores'], dtype=torch.float64, requires_grad=True)
        original = raw.detach().clone()
        mask = torch.tensor(fixture['mask'], dtype=torch.bool)
        batch = build_features(raw, fixture['query_texts'], fixture['page_ids'], mask,
                               query_length_cap=config['features']['query_length_cap'])
        labels = torch.tensor(fixture['labels_for_loss_only'], dtype=torch.float64)
        write_json(run.path/'features.json', {'names': FEATURE_NAMES, 'values': batch.values.tolist(),
                   'normalized_scores': batch.scores.tolist(), 'mask': batch.mask.tolist()})
        methods, traces, predictions, parameters = {}, [], {}, {}
        initial_parameters = None
        for name, granularity in [('QARF', 'query'), ('QPAF', 'page')]:
            model = make_model(config, granularity).double()
            initial = {key: value.detach().clone() for key, value in model.state_dict().items()}
            if initial_parameters is None:
                initial_parameters = initial
            elif any(not torch.equal(value, initial_parameters[key]) for key, value in initial.items()):
                raise RuntimeError('Matched variants did not start from identical gate parameters')
            optimizer = torch.optim.SGD(model.parameters(), lr=config['verification']['learning_rate'])
            before = model(batch)
            first_loss = pairwise_logistic_loss(before.scores, labels, mask)
            predictions[name] = {'weights_initial': before.weights.detach().tolist(),
                                 'scores_initial': before.scores.detach().tolist()}
            gradient_initial = None
            for step in range(config['verification']['steps']):
                optimizer.zero_grad(set_to_none=True)
                loss = pairwise_logistic_loss(model(batch).scores, labels, mask).loss
                loss.backward()
                gradients = [p.grad for p in model.parameters()]
                if any(g is None or not torch.isfinite(g).all() for g in gradients):
                    raise RuntimeError(f'{name}: missing or nonfinite gate gradient')
                gradient = sum(g.abs().sum().item() for g in gradients)
                if gradient_initial is None:
                    gradient_initial = gradient
                traces.append({'method': name, 'step': step, 'fixture_loss': loss.item(), 'gradient_l1': gradient})
                optimizer.step()
            after = model(batch)
            last_loss = pairwise_logistic_loss(after.scores, labels, mask).loss.item()
            frozen = raw.grad is None and torch.equal(raw.detach(), original)
            if not frozen or gradient_initial <= 0 or not last_loss < first_loss.loss.item():
                raise RuntimeError(f'{name}: fixture learning/frozen-retriever check failed')
            predictions[name].update(weights_final=after.weights.detach().tolist(), scores_final=after.scores.detach().tolist())
            parameters[name] = {key: value.detach().tolist() for key, value in model.state_dict().items()}
            methods[name] = {'granularity': granularity, 'parameter_count': sum(p.numel() for p in model.parameters()),
                             'loss_initial': first_loss.loss.item(), 'loss_final': last_loss,
                             'gradient_l1_initial': gradient_initial, 'retriever_frozen': frozen,
                             'valid_queries': first_loss.valid_queries, 'skipped_queries': first_loss.skipped_queries,
                             'pairs': first_loss.pairs}
            run.logger.info('%s fixture loss %.6f -> %.6f; gate gradient L1 %.6f; retriever frozen=%s',
                            name, first_loss.loss.item(), last_loss, gradient_initial, frozen)
        write_csv(run.path/'learning_trace.csv', traces)
        write_json(run.path/'predictions.json', predictions)
        write_json(run.path/'gate_parameters.json', parameters)
        summary = {'kind': 'synthetic_software_verification', 'software_verification': 'passed',
                   'independent_review': 'pending', 'real_data_experiment': 'not_run',
                   'feature_schema': config['features']['schema'], 'feature_count': len(FEATURE_NAMES),
                   'unit_tests': tests, 'methods': methods, 'torch': torch.__version__,
                   'dtype': 'float64', 'device': 'cpu', 'seed': config['verification']['seed']}
        write_json(run.path/'summary.json', summary)
        lines = ['# M1.2 method-core verification', '',
                 '**Software verification: PASS. Kind: synthetic_software_verification.**', '',
                 f'Unit tests: {result.testsRun}, failures: 0, errors: 0, skipped: 0.',
                 f'Feature schema: {config["features"]["schema"]}; 13 label-free features.',
                 f'Gate: {config["gate"]["kind"]}; query pooling for QARF, per-page conditioning for QPAF.',
                 'Inputs, feature construction, parameter budget, initial parameters and loss are matched.',
                 'Checks include hand arithmetic, ties/padding, finite differences for both gate architectures,',
                 'query-balanced pairwise loss, gradient flow and frozen retriever boundaries.', '',
                 '| Method | Parameters | Initial fixture loss | Final fixture loss | Initial gradient L1 |',
                 '| --- | --- | --- | --- | --- |']
        for name, values in methods.items():
            lines.append(f'| {name} | {values["parameter_count"]} | {values["loss_initial"]:.8f} | '
                         f'{values["loss_final"]:.8f} | {values["gradient_l1_initial"]:.8f} |')
        lines.extend(['', 'These losses only demonstrate that the implementation can learn on the fixture.',
                      'They do not measure retrieval quality or show learned QPAF superiority.',
                      'Real-data trainer/evaluator: M2.4. Matched learned pilot: M3.',
                      'Independent review / reproduction by another member: PENDING.',
                      'Source, config, fixture hashes, command and environment: provenance.json.',
                      'Output integrity: hashes.csv and receipt.json; complete.json links the receipt.', ''])
        (run.path/'verification.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'Verification evidence: {run.path}')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ValueError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2)
