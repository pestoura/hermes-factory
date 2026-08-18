from hermes_factory import agents


def test_profile_evaluation_api_is_exposed() -> None:
    names = (
        "ProfileAdmissionError",
        "ProfileEvalEvidence",
        "ProfileEvalHarness",
        "ProfileEvalRecord",
        "ProfileEvalState",
    )
    missing = [name for name in names if getattr(agents, name, None) is None]

    assert not missing, f"missing Profile evaluation API: {missing}"
