from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from hermes_factory.workflow import HITLRequest, HITLState, HumanDecision


class GatewayHITLProjectionError(ValueError):
    pass


class GatewaySendResult(Protocol):
    success: bool
    message_id: str | None


class GatewayClarifySender(Protocol):
    async def send_clarify(
        self,
        chat_id: str,
        question: str,
        choices: list[str],
        clarify_id: str,
        session_key: str,
        metadata: dict[str, object] | None = None,
    ) -> GatewaySendResult: ...


@dataclass(frozen=True)
class GatewayHITLCallback:
    clarify_id: str
    responder_identity: str
    choice: str


@dataclass(frozen=True)
class GatewayHITLProjection:
    request_id: str
    request_version: int
    context_revision: str
    candidate_revision: str | None
    clarify_id: str
    platform: str
    chat_id: str
    session_key: str
    question: str
    choices: tuple[str, ...]
    allowed_responder: str
    surface: str = "send_clarify"

    def gateway_kwargs(self) -> dict[str, object]:
        return {
            "chat_id": self.chat_id,
            "question": self.question,
            "choices": list(self.choices),
            "clarify_id": self.clarify_id,
            "session_key": self.session_key,
        }


@dataclass(frozen=True)
class GatewayHITLDelivery:
    platform: str
    chat_id: str
    clarify_id: str
    message_id: str


class HermesGatewayHITLBinding:
    """Bind Factory HITL projections to Hermes' native PlatformAdapter surface."""

    def __init__(
        self,
        *,
        platform_name: str,
        platform_adapter: GatewayClarifySender,
    ) -> None:
        normalized = platform_name.strip().lower()
        if not normalized:
            raise ValueError("Hermes Gateway platform name is required")
        self._platform_name = normalized
        self._platform_adapter = platform_adapter

    async def deliver(self, projection: GatewayHITLProjection) -> GatewayHITLDelivery:
        if projection.platform != self._platform_name:
            raise GatewayHITLProjectionError(
                "HITL projection platform does not match Hermes Gateway binding"
            )

        result = await self._platform_adapter.send_clarify(
            chat_id=projection.chat_id,
            question=projection.question,
            choices=list(projection.choices),
            clarify_id=projection.clarify_id,
            session_key=projection.session_key,
            metadata=None,
        )
        if not result.success:
            raise GatewayHITLProjectionError("Hermes Gateway send_clarify failed")
        if result.message_id is None or not str(result.message_id).strip():
            raise GatewayHITLProjectionError(
                "Hermes Gateway send_clarify returned no message identity"
            )

        return GatewayHITLDelivery(
            platform=projection.platform,
            chat_id=projection.chat_id,
            clarify_id=projection.clarify_id,
            message_id=str(result.message_id),
        )


class HermesGatewayHITLAdapter:
    def __init__(self, *, redact_text: Callable[[str], str]) -> None:
        self._redact_text = redact_text

    def project_clarify(
        self,
        request: HITLRequest,
        *,
        chat_id: str,
        session_key: str,
        question: str,
        choices: tuple[str, ...],
    ) -> GatewayHITLProjection:
        if request.state is not HITLState.PENDING:
            raise GatewayHITLProjectionError("only pending HITL requests can be projected")
        if not request.request_id.strip() or request.request_version < 1:
            raise GatewayHITLProjectionError("valid HITL request identity is required")
        if not chat_id.strip() or not session_key.strip():
            raise GatewayHITLProjectionError("Hermes Gateway routing is required")
        if not question.strip():
            raise GatewayHITLProjectionError("HITL question is required")
        if len(choices) < 2 or any(not choice.strip() for choice in choices):
            raise GatewayHITLProjectionError("at least two non-empty HITL choices are required")
        if len(set(choices)) != len(choices):
            raise GatewayHITLProjectionError("HITL choices must be unique")

        platform, separator, _ = request.allowed_responder.partition(":")
        if not separator or not platform.strip():
            raise GatewayHITLProjectionError(
                "allowed responder must carry a Hermes Gateway platform identity"
            )

        self._assert_public(question)
        for choice in choices:
            self._assert_public(choice)

        return GatewayHITLProjection(
            request_id=request.request_id,
            request_version=request.request_version,
            context_revision=request.context_revision,
            candidate_revision=request.candidate_revision,
            clarify_id=self._clarify_id(request),
            platform=platform,
            chat_id=chat_id,
            session_key=session_key,
            question=question,
            choices=choices,
            allowed_responder=request.allowed_responder,
        )

    def decision_from_callback(
        self,
        request: HITLRequest,
        projection: GatewayHITLProjection,
        callback: GatewayHITLCallback,
    ) -> HumanDecision:
        if request.state is not HITLState.PENDING:
            raise GatewayHITLProjectionError("only pending HITL requests can be decided")
        expected_identity = (
            request.request_id,
            request.request_version,
            request.context_revision,
            request.candidate_revision,
            request.allowed_responder,
        )
        projection_identity = (
            projection.request_id,
            projection.request_version,
            projection.context_revision,
            projection.candidate_revision,
            projection.allowed_responder,
        )
        if projection_identity != expected_identity:
            raise GatewayHITLProjectionError("HITL projection is stale or unbound")
        if projection.clarify_id != self._clarify_id(request):
            raise GatewayHITLProjectionError("HITL clarify identity does not match request")
        if callback.clarify_id != projection.clarify_id:
            raise GatewayHITLProjectionError("Gateway callback belongs to another prompt")
        if callback.responder_identity != request.allowed_responder:
            raise GatewayHITLProjectionError("Gateway callback responder is not authorized")
        if callback.choice not in projection.choices:
            raise GatewayHITLProjectionError("Gateway callback choice is not permitted")

        return HumanDecision(
            request_id=request.request_id,
            request_version=request.request_version,
            context_revision=request.context_revision,
            candidate_revision=request.candidate_revision,
            responder_identity=callback.responder_identity,
            decision=callback.choice,
        )

    def _assert_public(self, value: str) -> None:
        try:
            redacted = self._redact_text(value)
        except Exception as error:
            raise GatewayHITLProjectionError(
                "HITL redaction boundary could not verify public content"
            ) from error
        if redacted != value:
            raise GatewayHITLProjectionError(
                "sensitive material is forbidden in Hermes Gateway HITL payloads"
            )

    @staticmethod
    def _clarify_id(request: HITLRequest) -> str:
        identity = "\x1f".join(
            (
                request.request_id,
                str(request.request_version),
                request.context_revision,
                request.candidate_revision or "",
                request.allowed_responder,
            )
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"hf:{digest}"
