"""Offline verifier regression: corrupt, missing and unexpected retained payloads."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'scripts/source_materials.py'))
verify = helpers['verify']
restore = helpers['restore']


class MaterialsVerification(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.validation/source-verifier-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.path = Path(self.directory.name) / 'fixture.tar.gz'

    def tearDown(self):
        self.directory.cleanup()

    def archive(self, data=b'original source', missing=False, extra=False, duplicate=False, duplicate_rows=False):
        expected = b'original source'
        inventory = {'files': [{'archive_path': 'source-materials/sources/a.tar.gz', 'bytes': len(expected),
                                'sha256': hashlib.sha256(expected).hexdigest()}]}
        if duplicate_rows:
            inventory['files'] *= 2
        with tarfile.open(self.path, 'w:gz') as output:
            entries = [('source-materials/inventory.json', json.dumps(inventory).encode('utf-8'))]
            if duplicate:
                entries += entries[:]
            if not missing:
                entries.append(('source-materials/sources/a.tar.gz', data))
            if extra:
                entries.append(('source-materials/unexpected', b'x'))
            for name, payload in entries:
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                output.addfile(entry, io.BytesIO(payload))

    def test_complete_archive(self):
        self.archive()
        self.assertEqual(verify(self.path)['files'], 1)

    def test_corrupt_source_rejected(self):
        self.archive(data=b'corrupted bytes')
        with self.assertRaises(AssertionError):
            verify(self.path)

    def test_missing_source_rejected(self):
        self.archive(missing=True)
        with self.assertRaises(AssertionError):
            verify(self.path)

    def test_unlisted_and_duplicate_members_rejected(self):
        for kwargs in ({'extra': True}, {'duplicate': True}):
            with self.subTest(**kwargs):
                self.archive(**kwargs)
                with self.assertRaises(AssertionError):
                    verify(self.path)

    def test_duplicate_inventory_rows_rejected(self):
        self.archive(duplicate_rows=True)
        with self.assertRaises(AssertionError):
            verify(self.path)

    def test_restore_keeps_identical_input_and_refuses_replacement(self):
        self.archive()
        previous = restore.__globals__['CACHE']
        cache = Path(self.directory.name) / 'cache'
        restore.__globals__['CACHE'] = cache
        try:
            self.assertEqual(restore(self.path)['restored_cached_files'], 1)
            self.assertEqual(restore(self.path)['restored_cached_files'], 0)
            target = cache / 'materials/a.tar.gz'
            target.write_bytes(b'user changed cached input')
            with self.assertRaises(AssertionError):
                restore(self.path)
            self.assertEqual(target.read_bytes(), b'user changed cached input')
        finally:
            restore.__globals__['CACHE'] = previous


if __name__ == '__main__':
    unittest.main()
