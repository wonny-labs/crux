"""The image freeze accepts the workspace manifest checkout under its actual folder name and the historical one."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TARGET = Path(__file__).resolve().parents[1] / 'target'
sys.path.insert(0, str(TARGET))
import bench_image
import prepare_m5_network as subject


class CheckoutFolderName(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def linked(self, main, name, relative=False):
        gitdir = self.root / main / '.git' / 'worktrees' / name
        gitdir.mkdir(parents=True)
        (gitdir / 'commondir').write_text('../..\n')
        worktree = self.root / name
        worktree.mkdir()
        pointer = Path('..') / gitdir.relative_to(self.root) if relative else gitdir
        (worktree / '.git').write_text('gitdir: %s\n' % pointer)
        return worktree

    def test_a_plain_checkout_is_named_by_its_folder(self):
        for name in ('crux', 'crux-pilot'):
            (self.root / name / '.git').mkdir(parents=True)
            self.assertEqual(subject.checkout_folder_name(self.root / name), name)

    def test_a_linked_worktree_is_named_by_its_main_checkout(self):
        self.assertEqual(subject.checkout_folder_name(self.linked('crux', 'task-a')), 'crux')
        self.assertEqual(subject.checkout_folder_name(self.linked('crux-pilot', 'task-b', relative=True)),
                         'crux-pilot')

    def test_a_git_file_without_a_common_directory_keeps_the_folder_name(self):
        for name, pointer in (('submodule', '../elsewhere'), ('unreachable', '/nonexistent/.git/worktrees/x')):
            (self.root / name).mkdir()
            (self.root / name / '.git').write_text('gitdir: %s\n' % pointer)
            self.assertEqual(subject.checkout_folder_name(self.root / name), name)

    def test_the_tools_use_the_checkout_that_holds_them(self):
        self.assertEqual(subject.CHECKOUT_FOLDER, subject.checkout_folder_name(TARGET.parents[1]))


class ManifestContext(unittest.TestCase):
    def frozen(self, profile, context_path, others=()):
        pinned, paths = profile.locked()
        projects = [dict(name=k, revision=v, path=paths[k], git_commit=v, dirty=False) for k, v in pinned.items()]
        context = dict(name='manifest', path=context_path, revision='HEAD', git_commit='e' * 40, dirty=False)
        source = dict(git_commit='a' * 40, dirty=False, recoverable_from_git=True, snapshot_sha256='b' * 64)
        subject.frozen_inputs(dict(source=source, west_projects=[context, *projects, *others]), profile)

    def profiles(self):
        return subject.m5_profile(), bench_image.bench_profile()

    def test_accepts_the_actual_folder_name_and_the_historical_one(self):
        for folder in ('crux', 'crux-pilot'):
            with patch.object(subject, 'CHECKOUT_FOLDER', folder):
                for profile in self.profiles():
                    for path in (folder, 'crux-pilot'):
                        with self.subTest(folder=folder, profile=profile.name, path=path):
                            self.frozen(profile, path)

    def test_rejects_any_other_folder_name(self):
        with patch.object(subject, 'CHECKOUT_FOLDER', 'crux'):
            for profile in self.profiles():
                for path in ('crux-controller', '../crux', 'crux/'):
                    with self.subTest(profile=profile.name, path=path), self.assertRaises(ValueError):
                        self.frozen(profile, path)

    def test_no_other_project_may_overlap_either_manifest_checkout_name(self):
        with patch.object(subject, 'CHECKOUT_FOLDER', 'crux'):
            for path in ('crux', 'crux/sub', 'crux-pilot'):
                other = dict(name='other', revision='4' * 40, path=path, git_commit='4' * 40, dirty=False)
                with self.subTest(path=path), self.assertRaises(ValueError):
                    self.frozen(subject.m5_profile(), 'crux', [other])

    def test_a_product_profile_keeps_only_its_own_manifest_path(self):
        with patch.object(subject, 'CHECKOUT_FOLDER', 'crux'):
            self.frozen(subject.s2_profile(), 'crux-controller')
            for path in ('crux', 'crux-pilot'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    self.frozen(subject.s2_profile(), path)


if __name__ == '__main__':
    unittest.main()
