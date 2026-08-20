import asyncio
from dataclasses import dataclass

import hermes_factory.adapters.hermes_gateway as gateway
from hermes_factory.workflow import HITLRequest, HITLState


@dataclass
class _SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class _FakePlatformAdapter:
    def __init__(self, result: _SendResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def send_clarify(
        self,
        chat_id: str,
        question: str,
        choices: list[str],
        clarify_id: str,
        session_key: str,
        metadata: dict[str, object] | None = None,
    ) -> _SendResult:
        self.calls.append(
            {
                "chat_id": chat_id,
                "question": question,
                "choices": choices,
                "clarify_id": clarify_id,
                "session_key": session_key,
                "metadata": metadata,
            }
        )
        return self.result


def _binding_type():
    binding_type = getattr(gateway, "HermesGatewayHITLBinding", None)
    assert binding_type is not None, "HermesGatewayHITLBinding is not implemented"
    return binding_type


def _projection():
    request = HITLRequest(
        request_id="HITL-42",
        request_version=3,
        context_revision="ctx-9",
        candidate_revision="abc123",
        allowed_responder="telegram:1001",
        state=HITLState.PENDING,
    )
    adapter = gateway.HermesGatewayHITLAdapter(redact_text=lambda value: value)
    return adapter.project_clarify(
        request,
        chat_id="1001",
        session_key="telegram:1001:factory",
        question="Approve this bounded architecture decision?",
        choices=("approve", "reject"),
    )


def test_gateway_binding_delivers_projection_through_native_send_clarify() -> None:
    platform = _FakePlatformAdapter(_SendResult(success=True, message_id="msg-77"))
    binding = _binding_type()(
        platform_name="telegram",
        platform_adapter=platform,
    )

    projection = _projection()
    delivery = asyncio.run(binding.deliver(projection))

    assert platform.calls == [
        {
            "chat_id": "1001",
            "question": "Approve this bounded architecture decision?",
            "choices": ["approve", "reject"],
            "clarify_id": projection.clarify_id,
            "session_key": "telegram:1001:factory",
            "metadata": None,
        }
    ]
    assert delivery.platform == "telegram"
    assert delivery.chat_id == "1001"
    assert delivery.clarify_id == projection.clarify_id
    assert delivery.message_id == "msg-77"


def test_gateway_binding_rejects_projection_for_another_platform_before_send() -> None:
    platform = _FakePlatformAdapter(_SendResult(success=True, message_id="msg-77"))
    binding = _binding_type()(
        platform_name="discord",
        platform_adapter=platform,
    )

    try:
        asyncio.run(binding.deliver(_projection()))
    except gateway.GatewayHITLProjectionError as error:
        assert "platform" in str(error).lower()
    else:
        raise AssertionError("cross-platform HITL projection must fail closed")

    assert platform.calls == []


def test_gateway_binding_fails_closed_when_native_delivery_fails() -> None:
    platform = _FakePlatformAdapter(
        _SendResult(success=False, error="transport detail must not leak")
    )
    binding = _binding_type()(
        platform_name="telegram",
        platform_adapter=platform,
    )

    try:
        asyncio.run(binding.deliver(_projection()))
    except gateway.GatewayHITLProjectionError as error:
        assert str(error) == "Hermes Gateway send_clarify failed"
        assert "transport detail" not in str(error)
    else:
        raise AssertionError("failed Gateway delivery must fail closed")
