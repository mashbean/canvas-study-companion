import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('reader', ROOT/'scripts/build_reader.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class ReaderTests(unittest.TestCase):
    def pack(self):
        return json.loads((ROOT/'examples/demo-pack.json').read_text(encoding='utf-8'))

    def test_build_copies_assets_and_preserves_paragraph_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            out = r.build(ROOT/'examples/demo-pack.json', Path(folder)/'site')
            self.assertTrue((out/'assets/choices.png').is_file())
            saved = json.loads((out/'pack.js').read_text(encoding='utf-8').removeprefix('window.PACK = ').rstrip(';\n'))
            self.assertEqual(saved['documents'][0]['units'][0]['flow'][0]['id'], 'demo-choice-1')
            self.assertIn('<math', saved['documents'][0]['units'][1]['flow'][0]['en'])

    def test_html_strips_execution_and_unsafe_urls(self):
        raw = '<script>alert(1)</script><img src="https://tracking.example/a" onerror="bad()"><a href="javascript:alert(1)">A</a><svg onload="bad()"></svg><p onclick="bad()">Text</p>'
        clean = r.clean(raw)
        for unsafe in ['<script', '<svg', 'onerror', 'onclick', 'javascript:', 'tracking.example']:
            self.assertNotIn(unsafe, clean)
        self.assertIn('<p>Text</p>', clean)

    def test_missing_translation_requires_explicit_gap_but_english_only_does_not(self):
        pack = self.pack(); pair = pack['documents'][0]['units'][0]['flow'][0]; pair.pop('translation')
        with self.assertRaises(ValueError): r.prepare(pack)
        pair['translation_gap'] = 'Awaiting translation'; r.prepare(pack)
        pair.pop('translation_gap'); pack['language']['mode']='english-only'; r.prepare(pack)

    def test_rtl_and_duplicate_ids(self):
        pack=self.pack();pack['language'].update(code='ar',name='العربية',direction='rtl');r.prepare(pack)
        pack['documents'][0]['units'][0]['flow'][1]['id']='demo-choice-1'
        with self.assertRaises(ValueError):r.prepare(pack)

    def test_asset_cannot_escape_or_overwrite_app(self):
        for asset in ['../secret.env','app.js','assets/evil.js']:
            pack=self.pack();pack['assets']=[asset]
            with tempfile.TemporaryDirectory() as folder:
                p=Path(folder)/'pack.json';p.write_text(json.dumps(pack), encoding='utf-8')
                with self.assertRaises(ValueError):r.build(p,Path(folder)/'out')

    def test_script_closing_string_stays_data(self):
        pack=self.pack();pack['assets']=[];pack['title']='</script><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'pack.json';p.write_text(json.dumps(pack), encoding='utf-8');out=r.build(p,Path(folder)/'out')
            self.assertNotIn('</script>',(out/'pack.js').read_text(encoding='utf-8'))

if __name__ == '__main__':unittest.main()
