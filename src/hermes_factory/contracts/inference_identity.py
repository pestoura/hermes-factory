from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactoryInferenceIdentity:
    model: str
    provider: str
    base_url: str


CANONICAL_FACTORY_INFERENCE_IDENTITY = FactoryInferenceIdentity(
    model="tencent/hy3:free",
    provider="nous",
    base_url="https://inference-api.nousresearch.com/v1",
)
