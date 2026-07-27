from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from .models import InteractionEnvelope, InteractionKind


_MARKER_RE = re.compile(
    r"\[BOTMESH/1:"
    r"(?P<kind>REQ|REP|OBS|DSP):"
    r"(?P<interaction_id>[a-f0-9]{16,32}):"
    r"(?P<source>[A-Za-z0-9_.-]{1,64}):"
    r"(?P<target>[A-Za-z0-9_.-]{1,64}):"
    r"(?P<depth>\d{1,3}):"
    r"(?P<created_at>\d{10}):"
    r"(?P<signature>[a-f0-9]{32}|[a-f0-9]{16}|-)\]"
)

# Unicode tag characters are invisible in normal chat rendering while surviving
# ordinary JSON/text transport. Each printable ASCII marker character maps to
# one tag code point; the sentinels let us reject truncated/corrupted frames.
_HIDDEN_START = "\u2063\U000e0001"
_HIDDEN_END = "\U000e007f\u2063"
_HIDDEN_RE = re.compile(
    re.escape(_HIDDEN_START)
    + r"(?P<tagged>[\U000e0020-\U000e007e]+)"
    + re.escape(_HIDDEN_END)
)

MIN_SHARED_SECRET_BYTES = 32
SIGNATURE_HEX_CHARS = 32


class ProtocolError(ValueError):
    """Raised when a BotMesh marker exists but cannot be trusted."""


class ProtocolCodec:
    def __init__(
        self,
        shared_secret: str = "",
        *,
        fallback_shared_secret: str = "",
        require_signature: bool = True,
        accept_legacy_signatures: bool = False,
    ):
        self.shared_secret, self.secret_error = self._validated_secret(
            shared_secret, label="shared_secret"
        )
        self.fallback_shared_secret, self.fallback_secret_error = self._validated_secret(
            fallback_shared_secret,
            label="fallback_shared_secret",
        )
        self.require_signature = bool(require_signature)
        self.accept_legacy_signatures = bool(accept_legacy_signatures)

    @property
    def is_ready(self) -> bool:
        return bool(self.shared_secret) or not self.require_signature

    @staticmethod
    def _validated_secret(value: str, *, label: str) -> tuple[bytes, str]:
        text = str(value or "").strip()
        if not text:
            return b"", ""
        encoded = text.encode("utf-8")
        if len(encoded) < MIN_SHARED_SECRET_BYTES:
            return (
                b"",
                f"{label} 至少需要 {MIN_SHARED_SECRET_BYTES} 个 UTF-8 字节",
            )
        return encoded, ""

    def new_request(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        depth: int = 0,
        now: int | None = None,
    ) -> InteractionEnvelope:
        return self._build(
            "REQ",
            secrets.token_hex(10),
            source_bot_id,
            target_bot_id,
            depth,
            int(now if now is not None else time.time()),
        )

    def reply_to(
        self,
        request: InteractionEnvelope,
        *,
        now: int | None = None,
    ) -> InteractionEnvelope:
        if not request.is_request:
            raise ProtocolError("只能对 REQ 信封创建 REP")
        return self._build(
            "REP",
            request.interaction_id,
            request.target_bot_id,
            request.source_bot_id,
            request.depth + 1,
            int(now if now is not None else time.time()),
        )

    def new_observation(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        now: int | None = None,
    ) -> InteractionEnvelope:
        return self._build(
            "OBS",
            secrets.token_hex(10),
            source_bot_id,
            target_bot_id,
            0,
            int(now if now is not None else time.time()),
        )

    def new_display(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        interaction_id: str | None = None,
        depth: int = 0,
        now: int | None = None,
    ) -> InteractionEnvelope:
        return self._build(
            "DSP",
            interaction_id or secrets.token_hex(10),
            source_bot_id,
            target_bot_id,
            depth,
            int(now if now is not None else time.time()),
        )

    def _build(
        self,
        kind: InteractionKind,
        interaction_id: str,
        source_bot_id: str,
        target_bot_id: str,
        depth: int,
        created_at: int,
    ) -> InteractionEnvelope:
        return InteractionEnvelope(
            kind=kind,
            interaction_id=interaction_id,
            source_bot_id=source_bot_id,
            target_bot_id=target_bot_id,
            depth=int(depth),
            created_at=int(created_at),
        )

    def bind_content(
        self, envelope: InteractionEnvelope, content: str
    ) -> InteractionEnvelope:
        cleaned = str(content or "").strip()
        signature = self._signature(envelope, cleaned)
        return InteractionEnvelope(
            kind=envelope.kind,
            interaction_id=envelope.interaction_id,
            source_bot_id=envelope.source_bot_id,
            target_bot_id=envelope.target_bot_id,
            depth=envelope.depth,
            created_at=envelope.created_at,
            signature=signature,
        )

    def marker(self, envelope: InteractionEnvelope) -> str:
        signature = envelope.signature
        if not signature:
            raise ProtocolError("必须先用 bind_content/attach 将正文绑定到协议信封")
        return (
            f"[BOTMESH/1:{envelope.kind}:{envelope.interaction_id}:"
            f"{envelope.source_bot_id}:{envelope.target_bot_id}:"
            f"{envelope.depth}:{envelope.created_at}:{signature}]"
        )

    def attach(
        self,
        content: str,
        envelope: InteractionEnvelope,
        *,
        hidden: bool = True,
    ) -> str:
        cleaned = str(content or "").strip()
        bound = self.bind_content(envelope, cleaned)
        marker = self.marker(bound)
        if not hidden:
            return f"{cleaned}\n\u200b{marker}"
        hidden = "".join(chr(0xE0000 + ord(char)) for char in marker)
        return f"{cleaned}{_HIDDEN_START}{hidden}{_HIDDEN_END}"

    @staticmethod
    def has_protocol_hint(message: str) -> bool:
        text = str(message or "")
        return "[BOTMESH/1:" in text or _HIDDEN_START in text

    def extract(self, message: str) -> tuple[InteractionEnvelope | None, str]:
        text = str(message or "")
        hidden_match = _HIDDEN_RE.search(text)
        if hidden_match is not None:
            try:
                marker_text = "".join(
                    chr(ord(char) - 0xE0000)
                    for char in hidden_match.group("tagged")
                )
            except (ValueError, OverflowError) as exc:
                raise ProtocolError("隐藏 BotMesh 协议封包无效") from exc
            match = _MARKER_RE.fullmatch(marker_text)
            if match is None:
                raise ProtocolError("隐藏 BotMesh 协议封包无效")
            clean_content = (
                text[: hidden_match.start()] + text[hidden_match.end() :]
            ).strip(" \n\t\u200b\u2063")
            envelope = self._envelope_from_match(match)
            self.verify(envelope, clean_content)
            return envelope, clean_content
        if _HIDDEN_START in text:
            raise ProtocolError("隐藏 BotMesh 协议封包不完整")
        match = _MARKER_RE.search(text)
        if not match:
            return None, text.strip()
        envelope = self._envelope_from_match(match)
        clean_content = (text[: match.start()] + text[match.end() :]).strip(" \n\t\u200b")
        self.verify(envelope, clean_content)
        return envelope, clean_content

    @staticmethod
    def _envelope_from_match(match: re.Match[str]) -> InteractionEnvelope:
        return InteractionEnvelope(
            kind=match.group("kind"),  # type: ignore[arg-type]
            interaction_id=match.group("interaction_id"),
            source_bot_id=match.group("source"),
            target_bot_id=match.group("target"),
            depth=int(match.group("depth")),
            created_at=int(match.group("created_at")),
            signature=match.group("signature"),
        )

    def verify(self, envelope: InteractionEnvelope, content: str) -> None:
        if envelope.signature == "-":
            if self.require_signature:
                raise ProtocolError("BotMesh 消息未签名")
            return
        if len(envelope.signature) == 16 and not self.accept_legacy_signatures:
            raise ProtocolError("拒绝旧版 64-bit BotMesh 签名")
        secrets_to_try = tuple(
            secret
            for secret in (self.shared_secret, self.fallback_shared_secret)
            if secret
        )
        if not secrets_to_try:
            raise ProtocolError("本实例没有配置 shared_secret，无法校验消息")
        signature_length = len(envelope.signature)
        valid = False
        for secret in secrets_to_try:
            expected = self._signature_with_secret(
                secret,
                envelope,
                str(content or "").strip(),
            )[:signature_length]
            valid = hmac.compare_digest(expected, envelope.signature) or valid
        if not valid:
            raise ProtocolError("BotMesh 消息签名无效")

    def _signature(self, envelope: InteractionEnvelope, content: str) -> str:
        if not self.shared_secret:
            if self.require_signature:
                return "-"
            return "-"
        return self._signature_with_secret(self.shared_secret, envelope, content)

    @staticmethod
    def _signature_with_secret(
        secret: bytes,
        envelope: InteractionEnvelope,
        content: str,
    ) -> str:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        payload = ":".join(
            [
                envelope.kind,
                envelope.interaction_id,
                envelope.source_bot_id,
                envelope.target_bot_id,
                str(envelope.depth),
                str(envelope.created_at),
                content_hash,
            ]
        ).encode("utf-8")
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()[
            :SIGNATURE_HEX_CHARS
        ]
