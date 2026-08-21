---
name: factory-classifying-findings
description: Classify failures before corrective work is assigned.
version: 0.1.0
author: Pedro Estoura, Hermes Factory
license: MIT
metadata:
  factory:
    lifecycle: proposed
    test_status: not_run
    scope: corrective-action
    managed_by: hermes-factory
---

# Classifying Findings

## Purpose

Convert a material failure or adverse observation into a traceable Finding with the correct defect/problem class before rework is staffed.

## Procedure

1. Bind the Finding to source gate/UAT/review/runtime observation and affected requirement/WP/stage.
2. Record candidate/context identity and preserve original failure evidence.
3. Select the narrowest supported classification from the canonical Finding vocabulary.
4. Record impact/severity where applicable and set root-cause state to known or `UNKNOWN`.
5. Identify the capability/profession needed for diagnosis or correction.
6. Define verification requirements before creating a Rework Order.

## Invariants

- Do not hide repeated failure by superficial reclassification.
- `PRODUCT_DECISION_REQUIRED` and `EXTERNAL_BLOCKER` are not implementation defects.
- Classification is evidence-based; uncertainty remains explicit.
