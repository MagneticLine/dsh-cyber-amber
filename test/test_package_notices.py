"""Actual archive regression for missing, altered and non-regular notices."""
import io
from pathlib import Path
import runpy
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'scripts/package-notices.py'))


class PackageNotices(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.validation/package-notice-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temporary.name)
        for name in helpers['REQUIRED']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('preserved ' + name).encode('utf-8'))
        (self.root / 'NOTICE.md').write_text('vendor/SOURCE_MATERIAL_NOTICES.txt vendor/NATIVE_SOURCE_NOTICES.txt', encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, omit=None, alter=None, duplicate=None, link=None):
        path = self.root / 'fixture.tgz'
        with tarfile.open(path, 'w:gz') as archive:
            for name in helpers['REQUIRED']:
                if name == omit:
                    continue
                data = b'changed notice' if name == alter else (self.root / name).read_bytes()
                member = tarfile.TarInfo('package/' + name)
                if name == link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = 'elsewhere'
                    archive.addfile(member)
                    continue
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
                if name == duplicate:
                    archive.addfile(member, io.BytesIO(data))
        return path

    def verify(self, **kwargs):
        with tarfile.open(self.archive(**kwargs), 'r:gz') as archive:
            return helpers['verify_notices'](archive, self.root)

    def test_complete_payload(self):
        result = self.verify()
        self.assertTrue(result['verified'])
        self.assertEqual(len(result['files']), len(helpers['REQUIRED']))

    def test_missing_aggregate_rejected(self):
        with self.assertRaises(AssertionError):
            self.verify(omit='vendor/NATIVE_SOURCE_NOTICES.txt')

    def test_changed_upstream_license_rejected(self):
        with self.assertRaises(AssertionError):
            self.verify(alter='vendor/licenses/GPL-3.0.txt')

    def test_duplicate_and_symlink_rejected(self):
        for option in ('duplicate', 'link'):
            with self.subTest(option=option), self.assertRaises(AssertionError):
                self.verify(**{option: 'NOTICE.md'})


if __name__ == '__main__':
    unittest.main()
