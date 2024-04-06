import json
from typing import Type

from reqless.abstract import AbstractJob, AbstractJobData, AbstractJobProcessor
from reqless_test.common import TestReqless


class JobData(dict, AbstractJobData):
    @classmethod
    def from_json(cls, data: str) -> "JobData":
        return JobData(**json.loads(data))

    def to_json(self) -> str:
        return json.dumps(self)


class JobProcessorWithAnnotatedDataClass(AbstractJobProcessor[JobData]):
    @classmethod
    def process(cls, job: AbstractJob) -> None:
        pass


class JobProcessorWithExplicitDataClass(AbstractJobProcessor):
    @classmethod
    def data_class(cls) -> Type[JobData]:
        return JobData

    @classmethod
    def process(cls, job: AbstractJob) -> None:
        pass


class TestJobProcessorAPI(TestReqless):
    def test_data_class_can_be_determined_from_type_annotation(self) -> None:
        """The data class type can be inferred from type annotations"""
        self.assertEqual(JobData, JobProcessorWithAnnotatedDataClass.data_class())

    def test_data_class_can_be_explicitly_declared(self) -> None:
        """The data class type can be explicitly declared"""
        self.assertEqual(JobData, JobProcessorWithExplicitDataClass.data_class())

    def test_deserialize_data_json_returns_an_instance_of_data_class(self) -> None:
        """It deserializes the data to an instance of the data class"""
        data = JobData(foo="bar")
        data_json = data.to_json()
        for _class in [
            JobProcessorWithAnnotatedDataClass,
            JobProcessorWithExplicitDataClass,
        ]:
            self.assertEqual(data, _class.deserialize_data_json(data_json))
