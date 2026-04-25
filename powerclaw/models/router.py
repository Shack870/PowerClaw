from __future__ import annotations

"""Model routing primitives for the PowerClaw runtime."""

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from powerclaw.runtime.state import MessageRecord


@dataclass(slots=True)
class ModelRequest:
    """Runtime request passed to a model provider."""

    messages: Sequence[MessageRecord]
    preferred_model: str | None = None
    tools: Sequence[dict[str, Any]] = ()
    required_capabilities: tuple[str, ...] = ()
    iteration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelToolCall:
    """Normalized tool-call request returned by a model provider."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable tool-call payload."""
        return {
            "id": self.call_id,
            "name": self.name,
            "arguments": dict(self.arguments),
        }


@dataclass(slots=True)
class ModelResponse:
    """Normalized response returned from a model provider."""

    model: str
    content: str = ""
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    raw: Any = None

    def requests_tools(self) -> bool:
        """Return True when the model wants the runtime to execute tools."""
        return bool(self.tool_calls)


@dataclass(slots=True)
class ModelProviderDiagnostic:
    """Operator-facing state for a configured model provider."""

    name: str
    available: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable diagnostic payload."""
        return {
            "name": self.name,
            "available": self.available,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


class ModelProvider(Protocol):
    """Provider contract for model backends."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        ...


class ModelRouter:
    """Routes runtime requests through PowerClaw-owned provider abstractions."""

    def __init__(self, default_model: str = "gpt-5.4") -> None:
        self.default_model = default_model
        self._providers: dict[str, ModelProvider] = {}
        self._diagnostics: dict[str, ModelProviderDiagnostic] = {}

    def register_provider(
        self,
        name: str,
        provider: ModelProvider,
        *,
        reason: str = "registered",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Attach a provider implementation to the router."""
        self._providers[name] = provider
        self._diagnostics[name] = ModelProviderDiagnostic(
            name=name,
            available=True,
            reason=reason,
            metadata=metadata or {},
        )

    def register_unavailable_provider(
        self,
        name: str,
        reason: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a configured provider that cannot currently serve requests."""
        self._providers.pop(name, None)
        self._diagnostics[name] = ModelProviderDiagnostic(
            name=name,
            available=False,
            reason=reason,
            metadata=metadata or {},
        )

    def has_providers(self) -> bool:
        """Return True when at least one provider is available."""
        return bool(self._providers)

    def provider_names(self) -> list[str]:
        """Return available provider names in registration order."""
        return list(self._providers)

    def diagnostics(self) -> list[ModelProviderDiagnostic]:
        """Return provider diagnostics in deterministic order."""
        return [self._diagnostics[name] for name in sorted(self._diagnostics)]

    def diagnostics_summary(self) -> str:
        """Return a compact provider status string for CLI and scaffold messages."""
        if not self._diagnostics:
            return "no provider diagnostics recorded"
        parts = []
        for diagnostic in self.diagnostics():
            state = "available" if diagnostic.available else "unavailable"
            reason = f": {diagnostic.reason}" if diagnostic.reason else ""
            parts.append(f"{diagnostic.name} {state}{reason}")
        return "; ".join(parts)

    def resolve_model(self, request: ModelRequest) -> str:
        """Return the model id that should service the request."""
        return request.preferred_model or self.default_model

    def generate(
        self,
        request: ModelRequest,
        *,
        provider: str | None = None,
        allow_failover: bool = False,
    ) -> ModelResponse:
        """Dispatch a request to the selected provider."""
        if not self._providers:
            raise RuntimeError(f"no model providers registered ({self.diagnostics_summary()})")

        candidates = self._candidate_provider_names(provider=provider, allow_failover=allow_failover)
        failures: list[str] = []
        for provider_name in candidates:
            provider_impl = self._providers[provider_name]
            try:
                return provider_impl.generate(request)
            except Exception as exc:
                failures.append(f"{provider_name}: {type(exc).__name__}: {exc}")
                if not allow_failover:
                    raise

        raise RuntimeError(f"all model providers failed ({'; '.join(failures)})")

    def _candidate_provider_names(self, *, provider: str | None, allow_failover: bool) -> list[str]:
        if provider is None:
            return list(self._providers)
        if provider in self._providers:
            names = [provider]
            if allow_failover:
                names.extend(name for name in self._providers if name != provider)
            return names
        if allow_failover and self._providers:
            return list(self._providers)
        known = ", ".join(sorted(self._diagnostics or self._providers)) or "none"
        raise KeyError(f"unknown model provider: {provider}; known providers: {known}")
