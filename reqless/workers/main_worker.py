import _thread
import threading

from reqless.workers.serial_worker import SerialWorker
from reqless.workers.signals import basic_signal_handler, register_signal_handler


class MainWorker(SerialWorker):
    """A worker like SerialWorker, but that registers signals and expects to
    occupy the main thread."""

    def before_run(self) -> None:
        register_signal_handler(handler=basic_signal_handler(on_quit=self.stop))

    def halt_job_processing(self, jid: str) -> None:
        """Since this worker expects to occupy the main thread and this method
        is most likely to be called by the listener thread, we can interrupt
        the main thread to force a job to halt processing. We should probably
        only do this when called from a thread other than the main thread."""
        if threading.current_thread() is not threading.main_thread():
            _thread.interrupt_main()

    def run(self) -> None:
        self.before_run()
        super().run()
