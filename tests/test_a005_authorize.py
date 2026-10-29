"""A005 light authorization writer: files it writes must satisfy each stage's own guard."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005 import stage2, stage3, stage4  # noqa: E402
from qpaf.a005.authorize import write_authorization  # noqa: E402

APPROVAL = 'Tôi sẽ để cho bạn quyết định các task trong planning, miễn là nó sạch.'


class AuthorizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.cache = Path(self.tmp.name)/'repo', Path(self.tmp.name)/'cache'
        self.cache.mkdir()
        for name in stage2.CACHE_FILES:
            (self.cache/name).write_text(name, encoding='utf-8')
        for relative in {*stage2.SOURCES, *stage3.SOURCES, *stage4.SOURCES}:
            (self.root/relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root/relative).write_text(relative, encoding='utf-8')
        (self.root/stage2.OUTPUT).parent.mkdir(parents=True, exist_ok=True)
        (self.root/stage2.OUTPUT).write_text(json.dumps({'gate': {'status': 'PASS'}}), encoding='utf-8')
        (self.root/stage4.STAGE3).parent.mkdir(parents=True, exist_ok=True)
        (self.root/stage4.STAGE3).write_text('{}', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_stage2_authorization_passes_check(self):
        path = write_authorization(self.root, self.cache, 2, APPROVAL)
        self.assertEqual(path, self.root/stage2.AUTHORIZATION)
        stage2.check_authorization(self.root, self.cache)
        record = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((record['status'], record['stage'], record['approval_text']), ('APPROVED', 2, APPROVAL))

    def test_stage3_authorization_passes_check(self):
        write_authorization(self.root, self.cache, 3, APPROVAL)
        stage3.check_authorization(self.root, self.cache)

    def test_stage4_authorization_passes_check(self):
        path = write_authorization(self.root, self.cache, 4, APPROVAL, granularity='query', seed=stage4.SEEDS[0])
        self.assertEqual(path, stage4.run_dir(self.root, 'query', stage4.SEEDS[0])/'authorization.json')
        stage4.check_authorization(self.root, self.cache, 'query', stage4.SEEDS[0])

    def test_stage4_needs_run_arguments(self):
        with self.assertRaises(ValueError):
            write_authorization(self.root, self.cache, 4, APPROVAL)
        with self.assertRaises(ValueError):
            write_authorization(self.root, self.cache, 4, APPROVAL, granularity='query', seed=1)

    def test_empty_approval_text_refused(self):
        for text in ('', '   \n'):
            with self.assertRaises(ValueError):
                write_authorization(self.root, self.cache, 2, text)

    def test_refuses_overwrite(self):
        write_authorization(self.root, self.cache, 2, APPROVAL)
        with self.assertRaises(ValueError):
            write_authorization(self.root, self.cache, 2, APPROVAL)
        write_authorization(self.root, self.cache, 4, APPROVAL, granularity='page', seed=stage4.SEEDS[1])
        with self.assertRaises(ValueError):
            write_authorization(self.root, self.cache, 4, APPROVAL, granularity='page', seed=stage4.SEEDS[1])

    def test_stale_after_source_edit(self):
        write_authorization(self.root, self.cache, 2, APPROVAL)
        (self.root/stage2.SOURCES[1]).write_text('edited', encoding='utf-8')
        with self.assertRaisesRegex(stage2.Stage2Error, 'source differs'):
            stage2.check_authorization(self.root, self.cache)


if __name__ == '__main__':
    unittest.main()
