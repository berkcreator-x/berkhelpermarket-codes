"""Shared/cross-cutting services.

AI-specific services live in `src.ai`, payment-specific services live in
`src.payments`. This package is reserved for services shared across both
(e.g. future notification or analytics services) and is intentionally kept
minimal to enforce the strict separation between AI and billing logic.
"""
