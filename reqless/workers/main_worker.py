from reqless.workers.serial_worker import SerialWorker
from reqless.workers.signals import basic_signal_handler, register_signal_handler


class MainWorker(SerialWorker):
    """A worker like SerialWorker, but that registers signals and expects to
    occupy the main thread."""

    def before_run(self) -> None:
        register_signal_handler(handler=basic_signal_handler(on_quit=self.stop))

    def run(self) -> None:
        self.before_run()
        super().run()
