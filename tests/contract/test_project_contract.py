from pathlib import Path

import pytest

from hermes_factory.contracts import AcceptanceContract, ContractValidationError, ProjectContract


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_project_contract_loads_required_v1_2_fields(tmp_path):
    path = write(tmp_path, "project.yaml", """
schema: hermes.factory/project/v1.2
project:
  id: jarvas-cli
  name: Jarvas CLI
  repository: pestoura/jarvas-cli
  autonomy: governed
""")
    contract = ProjectContract.from_yaml(path)
    assert contract.project_id == "jarvas-cli"
    assert contract.repository == "pestoura/jarvas-cli"
    assert contract.autonomy == "governed"


def test_project_contract_rejects_unknown_top_level_field(tmp_path):
    path = write(tmp_path, "project.yaml", """
schema: hermes.factory/project/v1.2
project:
  id: jarvas-cli
  name: Jarvas CLI
  repository: pestoura/jarvas-cli
  autonomy: governed
unexpected: true
""")
    with pytest.raises(ContractValidationError, match="unknown"):
        ProjectContract.from_yaml(path)


def test_project_contract_rejects_missing_project_identity(tmp_path):
    path = write(tmp_path, "project.yaml", """
schema: hermes.factory/project/v1.2
project:
  name: Jarvas CLI
  repository: pestoura/jarvas-cli
  autonomy: governed
""")
    with pytest.raises(ContractValidationError, match="id"):
        ProjectContract.from_yaml(path)


def test_acceptance_contract_loads_explicit_uat_runtime_owner_flags(tmp_path):
    path = write(tmp_path, "acceptance.yaml", """
schema: hermes.factory/acceptance/v1.2
acceptance:
  uat_required: true
  runtime_required: true
  owner_acceptance_required: true
""")
    contract = AcceptanceContract.from_yaml(path)
    assert contract.uat_required is True
    assert contract.runtime_required is True
    assert contract.owner_acceptance_required is True


def test_acceptance_contract_rejects_implicit_or_missing_requirements(tmp_path):
    path = write(tmp_path, "acceptance.yaml", """
schema: hermes.factory/acceptance/v1.2
acceptance:
  uat_required: true
  runtime_required: true
""")
    with pytest.raises(ContractValidationError, match="owner_acceptance_required"):
        AcceptanceContract.from_yaml(path)
