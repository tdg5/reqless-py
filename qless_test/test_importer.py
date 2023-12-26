import mock

from qless.importer import Importer
from qless_test.common import TestQless


class ImporterTestClass:
    pass


class TestImporter(TestQless):
    def test_mark_for_reload_on_next_import(self) -> None:
        """Ensure that nothing blows up if we reload a class"""
        class_name = "qless_test.test_importer.ImporterTestClass"
        _class = Importer.import_class(class_name)
        self.assertEqual(_class, ImporterTestClass)
        Importer.mark_for_reload_on_next_import(class_name)
        _class = Importer.import_class(class_name)
        self.assertEqual(_class, ImporterTestClass)

    def test_no_mtime(self) -> None:
        """Don't blow up we cannot check the modification time of a module."""
        exc = OSError("Could not stat file")
        with mock.patch("qless.importer.os.stat", side_effect=exc):
            Importer.import_class("qless_test.test_job.Foo")
            Importer.import_class("qless_test.test_job.Foo")
