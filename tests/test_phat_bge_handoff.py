"""Exercise full-pool BGE joins across a static superset and a sparse supplement."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qpaf.jev.contracts import load_scores, write_json, write_scores


class HandoffTest(unittest.TestCase):
    def test_join_and_reject_incompatible_supplements(self):
        policy = dict(model="BAAI/bge-reranker-v2-m3", revision="fixture", max_length=1024,
                      dtype="float16", torch="fixture", packages=["fixture"], synthetic=True)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            def bundle(path, pairs):
                write_json(path, dict(dataset="vidoseek", partition="validation", top_k=2, synthetic=True,
                                      pairs=pairs, queries={q:q for q,p in pairs}, pages={p:p for q,p in pairs}))
            def execute(action, *extra):
                return subprocess.run([sys.executable,"-B",str(ROOT/"scripts/jev_phat_bge_handoff.py"),action,
                                       "--full",d/"full","--static",d/"old","--static-scores",d/"old_scores",
                                       *extra], capture_output=True,text=True)
            bundle(d/"full",[("a","y"),("b","z"),("a","x")])
            bundle(d/"old",[("a","x"),("b","z"),("extra","page")])
            write_scores(d/"old_scores",d/"old",[1,2,99],policy)
            result=execute("missing","--out",d/"slice")
            self.assertEqual(result.returncode,0,result.stderr)
            sl=json.loads((d/"slice").read_bytes())
            self.assertEqual(sl["queries"],{"a":"a"})
            join=("--extra",d/"slice","--extra-scores",d/"new","--out",d/"joined")
            write_scores(d/"new",d/"slice",[3],dict(policy,dtype="fp32"))
            self.assertNotEqual(execute("merge",*join).returncode,0)
            write_scores(d/"new",d/"slice",[3],policy)
            result=execute("merge",*join)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(load_scores(d/"joined",d/"full")["scores"],[3,2,1])
            sl["pages"]["y"]="different text"
            write_json(d/"slice",sl)
            write_scores(d/"new",d/"slice",[3],policy)
            self.assertNotEqual(execute("merge",*join[:-1],d/"wrong").returncode,0)
            self.assertFalse((d/"wrong").exists())


if __name__ == "__main__":
    unittest.main()
