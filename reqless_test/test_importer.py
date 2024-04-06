import mock

from reqless.importer import Importer
from reqless_test.common import TestReqless


class ImporterTestClass:
    pass


class TestImporter(TestReqless):
    def test_mark_for_reload_on_next_import(self) -> None:
        """Ensure that nothing blows up if we reload a class"""
        class_name = "reqless_test.test_importer.ImporterTestClass"
        _class = Importer.import_class(class_name)
        self.assertEqual(_class, ImporterTestClass)
        Importer.mark_for_reload_on_next_import(class_name)
        _class = Importer.import_class(class_name)
        self.assertEqual(_class, ImporterTestClass)

    def test_no_mtime(self) -> None:
        """Don't blow up we cannot check the modification time of a module."""
        exc = OSError("Could not stat file")
        with mock.patch("reqless.importer.os.stat", side_effect=exc):
            Importer.import_class("reqless_test.test_job.Foo")
            Importer.import_class("reqless_test.test_job.Foo")
