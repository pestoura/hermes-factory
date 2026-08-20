import importlib


def test_task_scoped_skill_preparer_runtime_exists() -> None:
    module = importlib.import_module("hermes_factory.runtime.task_skills")
    assert hasattr(module, "HermesTaskSkillPreparer")
