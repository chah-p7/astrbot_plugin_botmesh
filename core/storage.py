from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .models import InteractionEnvelope, Relation
from .social import RelationshipDelta, RelationshipState, context_digest


class InteractionStore:
    """Small SQLite audit store with duplicate-event protection."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    interaction_id TEXT PRIMARY KEY,
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    answer TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_events (
                    interaction_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    receiver_bot_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (interaction_id, kind, receiver_bot_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inferred_relations (
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    trust REAL NOT NULL,
                    tone TEXT NOT NULL DEFAULT '',
                    view_of_target TEXT NOT NULL DEFAULT '',
                    address_as TEXT NOT NULL DEFAULT '',
                    familiarity REAL NOT NULL DEFAULT 0,
                    affinity REAL NOT NULL DEFAULT 0,
                    romantic_interest REAL NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    evidence TEXT NOT NULL DEFAULT '',
                    prompt_hash TEXT NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (source_bot_id, target_bot_id)
                )
                """
            )
            inferred_columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(inferred_relations)"
                ).fetchall()
            }
            if "view_of_target" not in inferred_columns:
                connection.execute(
                    "ALTER TABLE inferred_relations "
                    "ADD COLUMN view_of_target TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relation_extraction_state (
                    source_bot_id TEXT PRIMARY KEY,
                    prompt_hash TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    unresolved_mentions TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_state (
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    active_mode TEXT NOT NULL DEFAULT '',
                    trust_delta REAL NOT NULL DEFAULT 0,
                    familiarity_delta REAL NOT NULL DEFAULT 0,
                    affinity_delta REAL NOT NULL DEFAULT 0,
                    romantic_interest_delta REAL NOT NULL DEFAULT 0,
                    last_reason TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (source_bot_id, target_bot_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_events (
                    event_id TEXT PRIMARY KEY,
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    context_digest TEXT NOT NULL,
                    active_mode TEXT NOT NULL DEFAULT '',
                    trust_delta REAL NOT NULL DEFAULT 0,
                    familiarity_delta REAL NOT NULL DEFAULT 0,
                    affinity_delta REAL NOT NULL DEFAULT 0,
                    romantic_interest_delta REAL NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_state_scoped (
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    group_id TEXT NOT NULL DEFAULT '',
                    active_mode TEXT NOT NULL DEFAULT '',
                    address_as_override TEXT NOT NULL DEFAULT '',
                    trust_delta REAL NOT NULL DEFAULT 0,
                    familiarity_delta REAL NOT NULL DEFAULT 0,
                    affinity_delta REAL NOT NULL DEFAULT 0,
                    romantic_interest_delta REAL NOT NULL DEFAULT 0,
                    last_reason TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (source_bot_id, target_bot_id, group_id)
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO relationship_state_scoped (
                    source_bot_id, target_bot_id, group_id, active_mode,
                    trust_delta, familiarity_delta, affinity_delta,
                    romantic_interest_delta, last_reason, version, updated_at
                )
                SELECT source_bot_id, target_bot_id, '', active_mode,
                       trust_delta, familiarity_delta, affinity_delta,
                       romantic_interest_delta, last_reason, version, updated_at
                FROM relationship_state
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship_events_scoped (
                    event_id TEXT PRIMARY KEY,
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    group_id TEXT NOT NULL DEFAULT '',
                    event_kind TEXT NOT NULL,
                    context_digest TEXT NOT NULL,
                    active_mode TEXT NOT NULL DEFAULT '',
                    address_as TEXT NOT NULL DEFAULT '',
                    address_changed INTEGER NOT NULL DEFAULT 0,
                    trust_delta REAL NOT NULL DEFAULT 0,
                    familiarity_delta REAL NOT NULL DEFAULT 0,
                    affinity_delta REAL NOT NULL DEFAULT 0,
                    romantic_interest_delta REAL NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO relationship_events_scoped (
                    event_id, source_bot_id, target_bot_id, group_id, event_kind,
                    context_digest, active_mode, trust_delta, familiarity_delta,
                    affinity_delta, romantic_interest_delta, confidence, reason,
                    created_at
                )
                SELECT event_id, source_bot_id, target_bot_id, '', event_kind,
                       context_digest, active_mode, trust_delta, familiarity_delta,
                       affinity_delta, romantic_interest_delta, confidence, reason,
                       created_at
                FROM relationship_events
                """
            )
            state_columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(relationship_state_scoped)"
                ).fetchall()
            }
            if "address_as_override" not in state_columns:
                connection.execute(
                    "ALTER TABLE relationship_state_scoped "
                    "ADD COLUMN address_as_override TEXT NOT NULL DEFAULT ''"
                )
            event_columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(relationship_events_scoped)"
                ).fetchall()
            }
            if "address_as" not in event_columns:
                connection.execute(
                    "ALTER TABLE relationship_events_scoped "
                    "ADD COLUMN address_as TEXT NOT NULL DEFAULT ''"
                )
            if "address_changed" not in event_columns:
                connection.execute(
                    "ALTER TABLE relationship_events_scoped "
                    "ADD COLUMN address_changed INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observer_interjections (
                    interaction_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    origin_user_id TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (interaction_id, direction)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observed_groups (
                    bot_id TEXT NOT NULL,
                    platform_id TEXT NOT NULL DEFAULT '',
                    platform_group_id TEXT NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    PRIMARY KEY (bot_id, platform_group_id)
                )
                """
            )
            observer_columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(observer_interjections)"
                ).fetchall()
            }
            if "session_id" not in observer_columns:
                connection.execute(
                    "ALTER TABLE observer_interjections "
                    "ADD COLUMN session_id TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_updated "
                "ON interactions(updated_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_interaction_events_created "
                "ON interaction_events(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_relationship_events_created "
                "ON relationship_events(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_relationship_events_scoped_created "
                "ON relationship_events_scoped(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_observer_rate_target "
                "ON observer_interjections(direction, source_bot_id, "
                "target_bot_id, session_id, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_observer_rate_source "
                "ON observer_interjections(direction, source_bot_id, created_at)"
            )

    def remember_group(
        self,
        bot_id: str,
        platform_group_id: str,
        *,
        platform_id: str = "",
        seen_at: int | None = None,
    ) -> None:
        bot = str(bot_id or "").strip()[:64]
        raw_group = str(platform_group_id or "").strip()[:128]
        if not bot or not raw_group:
            return
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO observed_groups (
                    bot_id, platform_id, platform_group_id, last_seen_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(bot_id, platform_group_id) DO UPDATE SET
                    platform_id=excluded.platform_id,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    bot,
                    str(platform_id or "").strip()[:128],
                    raw_group,
                    int(time.time() if seen_at is None else seen_at),
                ),
            )

    def observed_groups(self, limit: int = 500) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 2000))
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT bot_id, platform_id, platform_group_id, last_seen_at
                FROM observed_groups
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def prune(self, *, older_than: int) -> dict[str, int]:
        """Bound append-only audit data while preserving current relation state."""
        cutoff = int(older_than)
        deleted: dict[str, int] = {}
        with self._lock, self._transaction() as connection:
            for table, column in (
                ("interaction_events", "created_at"),
                ("observer_interjections", "created_at"),
                ("relationship_events", "created_at"),
                ("relationship_events_scoped", "created_at"),
                ("interactions", "updated_at"),
            ):
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE {column} < ?",
                    (cutoff,),
                )
                deleted[table] = max(0, int(cursor.rowcount))
        return deleted

    def record_outgoing(self, envelope: InteractionEnvelope, question: str) -> None:
        now = int(time.time())
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO interactions (
                    interaction_id, source_bot_id, target_bot_id, question,
                    status, depth, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'sent', ?, ?, ?)
                ON CONFLICT(interaction_id) DO UPDATE SET
                    question=excluded.question,
                    status='sent',
                    updated_at=excluded.updated_at
                """,
                (
                    envelope.interaction_id,
                    envelope.source_bot_id,
                    envelope.target_bot_id,
                    question,
                    envelope.depth,
                    envelope.created_at,
                    now,
                ),
            )

    def accept_event(self, envelope: InteractionEnvelope, receiver_bot_id: str) -> bool:
        with self._lock, self._transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO interaction_events (
                        interaction_id, kind, receiver_bot_id, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        envelope.interaction_id,
                        envelope.kind,
                        receiver_bot_id,
                        int(time.time()),
                    ),
                )
            except sqlite3.IntegrityError:
                return False
            if envelope.is_request:
                connection.execute(
                    """
                    INSERT INTO interactions (
                        interaction_id, source_bot_id, target_bot_id,
                        status, depth, created_at, updated_at
                    ) VALUES (?, ?, ?, 'processing', ?, ?, ?)
                    ON CONFLICT(interaction_id) DO UPDATE SET
                        status='processing', updated_at=excluded.updated_at
                    """,
                    (
                        envelope.interaction_id,
                        envelope.source_bot_id,
                        envelope.target_bot_id,
                        envelope.depth,
                        envelope.created_at,
                        int(time.time()),
                    ),
                )
            return True

    def set_question(self, interaction_id: str, question: str) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                "UPDATE interactions SET question=?, updated_at=? WHERE interaction_id=?",
                (question, int(time.time()), interaction_id),
            )

    def complete(self, interaction_id: str, answer: str) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                UPDATE interactions
                SET answer=?, status='replied', error='', updated_at=?
                WHERE interaction_id=?
                """,
                (answer, int(time.time()), interaction_id),
            )

    def fail(self, interaction_id: str, error: str) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                UPDATE interactions
                SET status='failed', error=?, updated_at=?
                WHERE interaction_id=?
                """,
                (error, int(time.time()), interaction_id),
            )

    def record_received_reply(self, envelope: InteractionEnvelope, answer: str) -> None:
        now = int(time.time())
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO interactions (
                    interaction_id, source_bot_id, target_bot_id, answer,
                    status, depth, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'reply_received', ?, ?, ?)
                ON CONFLICT(interaction_id) DO UPDATE SET
                    answer=excluded.answer,
                    status='reply_received',
                    updated_at=excluded.updated_at
                """,
                (
                    envelope.interaction_id,
                    envelope.target_bot_id,
                    envelope.source_bot_id,
                    answer,
                    envelope.depth,
                    envelope.created_at,
                    now,
                ),
            )

    def expects_reply(self, envelope: InteractionEnvelope, receiver_bot_id: str) -> bool:
        if not envelope.is_reply:
            return False
        with self._lock, self._transaction() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM interactions
                WHERE interaction_id=?
                  AND source_bot_id=?
                  AND target_bot_id=?
                  AND status='sent'
                """,
                (
                    envelope.interaction_id,
                    receiver_bot_id,
                    envelope.source_bot_id,
                ),
            ).fetchone()
        return row is not None

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT interaction_id, source_bot_id, target_bot_id, question,
                       answer, status, depth, created_at, updated_at, error
                FROM interactions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def inferred_prompt_hash(self, source_bot_id: str) -> str:
        with self._lock, self._transaction() as connection:
            row = connection.execute(
                """
                SELECT prompt_hash
                FROM relation_extraction_state
                WHERE source_bot_id=? AND status='ok'
                """,
                (source_bot_id,),
            ).fetchone()
        return str(row["prompt_hash"] if row else "")

    def replace_inferred_relations(
        self,
        source_bot_id: str,
        prompt_hash: str,
        relations: tuple[Relation, ...] | list[Relation],
        unresolved_mentions: tuple[str, ...] | list[str] = (),
    ) -> None:
        now = int(time.time())
        unresolved_text = "\n".join(str(item)[:300] for item in unresolved_mentions)
        with self._lock, self._transaction() as connection:
            connection.execute(
                "DELETE FROM inferred_relations WHERE source_bot_id=?",
                (source_bot_id,),
            )
            for relation in relations:
                if relation.source_bot_id != source_bot_id:
                    raise ValueError("推断关系的 source_bot_id 与同步主体不一致")
                connection.execute(
                    """
                    INSERT INTO inferred_relations (
                        source_bot_id, target_bot_id, relation_type, trust, tone,
                        view_of_target, address_as, familiarity, affinity, romantic_interest,
                        confidence, evidence, prompt_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relation.source_bot_id,
                        relation.target_bot_id,
                        relation.relation_type,
                        relation.trust,
                        relation.tone,
                        relation.view_of_target,
                        relation.address_as,
                        relation.familiarity,
                        relation.affinity,
                        relation.romantic_interest,
                        relation.confidence,
                        relation.evidence,
                        prompt_hash,
                        now,
                    ),
                )
            connection.execute(
                """
                INSERT INTO relation_extraction_state (
                    source_bot_id, prompt_hash, status, unresolved_mentions,
                    error, updated_at
                ) VALUES (?, ?, 'ok', ?, '', ?)
                ON CONFLICT(source_bot_id) DO UPDATE SET
                    prompt_hash=excluded.prompt_hash,
                    status='ok',
                    unresolved_mentions=excluded.unresolved_mentions,
                    error='',
                    updated_at=excluded.updated_at
                """,
                (source_bot_id, prompt_hash, unresolved_text, now),
            )

    def record_relation_extraction_error(
        self, source_bot_id: str, prompt_hash: str, error: str
    ) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO relation_extraction_state (
                    source_bot_id, prompt_hash, status, error, updated_at
                ) VALUES (?, ?, 'error', ?, ?)
                ON CONFLICT(source_bot_id) DO UPDATE SET
                    prompt_hash=excluded.prompt_hash,
                    status='error',
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (source_bot_id, prompt_hash, str(error)[:1000], int(time.time())),
            )

    def load_inferred_relations(
        self, *, inferred_allow_ask: bool = False
    ) -> list[Relation]:
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT source_bot_id, target_bot_id, relation_type, trust, tone,
                       view_of_target, address_as, familiarity, affinity, romantic_interest,
                       confidence, evidence, prompt_hash
                FROM inferred_relations
                ORDER BY source_bot_id, target_bot_id
                """
            ).fetchall()
        return [
            Relation.from_mapping(
                {
                    **dict(row),
                    "allow_ask": inferred_allow_ask,
                    "share_context": False,
                    "allow_flirt": False,
                    "origin": "system_prompt",
                }
            )
            for row in rows
        ]

    def relation_extraction_states(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT source_bot_id, prompt_hash, status,
                       unresolved_mentions, error, updated_at
                FROM relation_extraction_state
                ORDER BY source_bot_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_relationship_state(
        self,
        source_bot_id: str,
        target_bot_id: str,
        group_id: str = "",
    ) -> RelationshipState | None:
        with self._lock, self._transaction() as connection:
            row = connection.execute(
                """
                SELECT source_bot_id, target_bot_id, active_mode, trust_delta,
                       address_as_override, familiarity_delta, affinity_delta,
                       romantic_interest_delta, last_reason, version, updated_at
                FROM relationship_state_scoped
                WHERE source_bot_id=? AND target_bot_id=? AND group_id=?
                """,
                (source_bot_id, target_bot_id, str(group_id or "")[:128]),
            ).fetchone()
        return RelationshipState.from_mapping(dict(row)) if row else None

    def relationship_address_overrides(self) -> list[dict[str, Any]]:
        """Return active dynamic address overrides for administrator review."""
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT source_bot_id, target_bot_id, group_id,
                       address_as_override, last_reason, version, updated_at
                FROM relationship_state_scoped
                WHERE address_as_override <> ''
                ORDER BY group_id, source_bot_id, target_bot_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_relationship_address_override(
        self,
        source_bot_id: str,
        target_bot_id: str,
        group_id: str = "",
    ) -> bool:
        """Clear only the dynamic address while preserving other evolved state."""
        scope = str(group_id or "")[:128]
        now = int(time.time())
        with self._lock, self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE relationship_state_scoped
                SET address_as_override='', version=version + 1, updated_at=?
                WHERE source_bot_id=? AND target_bot_id=? AND group_id=?
                  AND address_as_override <> ''
                """,
                (now, source_bot_id, target_bot_id, scope),
            )
        return cursor.rowcount > 0

    def reset_relationship_state(
        self,
        source_bot_id: str,
        target_bot_id: str,
        group_id: str = "",
    ) -> bool:
        """Reset current dynamic state while retaining the append-only event audit."""
        scope = str(group_id or "")[:128]
        with self._lock, self._transaction() as connection:
            cursor = connection.execute(
                """
                DELETE FROM relationship_state_scoped
                WHERE source_bot_id=? AND target_bot_id=? AND group_id=?
                """,
                (source_bot_id, target_bot_id, scope),
            )
            # Prevent a migrated legacy global row from being copied back into the
            # scoped table on the next startup after an administrator reset.
            if not scope:
                connection.execute(
                    """
                    DELETE FROM relationship_state
                    WHERE source_bot_id=? AND target_bot_id=?
                    """,
                    (source_bot_id, target_bot_id),
                )
        return cursor.rowcount > 0

    def apply_relationship_delta(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        group_id: str = "",
        event_id: str,
        event_kind: str,
        context: str,
        delta: RelationshipDelta,
    ) -> bool:
        if not delta.accepted:
            return False
        now = int(time.time())
        with self._lock, self._transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO relationship_events_scoped (
                        event_id, source_bot_id, target_bot_id, group_id, event_kind,
                        context_digest, active_mode, address_as, address_changed, trust_delta,
                        familiarity_delta, affinity_delta,
                        romantic_interest_delta, confidence, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        source_bot_id,
                        target_bot_id,
                        str(group_id or "")[:128],
                        event_kind,
                        context_digest(context),
                        delta.active_mode,
                        delta.address_as or "",
                        1 if delta.address_as is not None else 0,
                        delta.trust_delta,
                        delta.familiarity_delta,
                        delta.affinity_delta,
                        delta.romantic_interest_delta,
                        delta.confidence,
                        delta.reason,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                return False

            row = connection.execute(
                """
                SELECT active_mode, trust_delta, familiarity_delta,
                       affinity_delta, romantic_interest_delta,
                       address_as_override, version
                FROM relationship_state_scoped
                WHERE source_bot_id=? AND target_bot_id=? AND group_id=?
                """,
                (source_bot_id, target_bot_id, str(group_id or "")[:128]),
            ).fetchone()
            current = dict(row) if row else {}
            active_mode = delta.active_mode or str(current.get("active_mode", ""))
            address_as_override = (
                str(delta.address_as or "")
                if delta.address_as is not None
                else str(current.get("address_as_override", ""))
            )
            trust_delta = _clamp_total(
                float(current.get("trust_delta", 0.0)) + delta.trust_delta, 0.5
            )
            familiarity_delta = _clamp_total(
                float(current.get("familiarity_delta", 0.0))
                + delta.familiarity_delta,
                0.5,
            )
            affinity_delta = _clamp_total(
                float(current.get("affinity_delta", 0.0)) + delta.affinity_delta,
                1.0,
            )
            romantic_delta = _clamp_total(
                float(current.get("romantic_interest_delta", 0.0))
                + delta.romantic_interest_delta,
                0.5,
            )
            version = int(current.get("version", 0)) + 1
            connection.execute(
                """
                INSERT INTO relationship_state_scoped (
                    source_bot_id, target_bot_id, group_id, active_mode,
                    address_as_override, trust_delta,
                    familiarity_delta, affinity_delta,
                    romantic_interest_delta, last_reason, version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_bot_id, target_bot_id, group_id) DO UPDATE SET
                    active_mode=excluded.active_mode,
                    address_as_override=excluded.address_as_override,
                    trust_delta=excluded.trust_delta,
                    familiarity_delta=excluded.familiarity_delta,
                    affinity_delta=excluded.affinity_delta,
                    romantic_interest_delta=excluded.romantic_interest_delta,
                    last_reason=excluded.last_reason,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                (
                    source_bot_id,
                    target_bot_id,
                    str(group_id or "")[:128],
                    active_mode,
                    address_as_override,
                    trust_delta,
                    familiarity_delta,
                    affinity_delta,
                    romantic_delta,
                    delta.reason,
                    version,
                    now,
                ),
            )
        return True

    def record_observer_interjection(
        self,
        envelope: InteractionEnvelope,
        *,
        direction: str,
        message: str,
        session_id: str = "",
        origin_user_id: str = "",
        reason: str = "",
    ) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO observer_interjections (
                    interaction_id, direction, source_bot_id, target_bot_id,
                    session_id, origin_user_id, message, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.interaction_id,
                    str(direction)[:16],
                    envelope.source_bot_id,
                    envelope.target_bot_id,
                    str(session_id)[:300],
                    str(origin_user_id)[:128],
                    str(message)[:4000],
                    str(reason)[:500],
                    int(time.time()),
                ),
            )

    def recent_observer_interjections(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT interaction_id, direction, source_bot_id, target_bot_id,
                       session_id, origin_user_id, message, reason, created_at
                FROM observer_interjections
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def observer_rate_status(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        session_id: str,
        since: int,
    ) -> tuple[int, int]:
        """Return (last target interjection time, source count since timestamp)."""
        with self._lock, self._transaction() as connection:
            last_row = connection.execute(
                """
                SELECT COALESCE(MAX(created_at), 0) AS last_created_at
                FROM observer_interjections
                WHERE direction='outgoing'
                  AND source_bot_id=? AND target_bot_id=? AND session_id=?
                """,
                (source_bot_id, target_bot_id, session_id),
            ).fetchone()
            count_row = connection.execute(
                """
                SELECT COUNT(*) AS event_count
                FROM observer_interjections
                WHERE direction='outgoing'
                  AND source_bot_id=? AND created_at>=?
                """,
                (source_bot_id, int(since)),
            ).fetchone()
        return (
            int(last_row["last_created_at"] if last_row else 0),
            int(count_row["event_count"] if count_row else 0),
        )


def _clamp_total(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))
