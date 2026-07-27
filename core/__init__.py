"""Pure-Python core for the BotMesh AstrBot plugin."""

from .autofill import (
    AUTOFILL_SYSTEM_PROMPT,
    AutofillError,
    AutofillResult,
    apply_autofill_response,
    build_autofill_prompt,
)
from .delivery import (
    DeliveryPlan,
    build_observation_delivery,
    build_reply_delivery,
    build_request_delivery,
)
from .editor import (
    RelationshipEditorError,
    node_to_config,
    normalize_node_entries,
    normalize_relation_entries,
    relation_to_config,
    relationship_editor_payload,
)
from .graph import BotGraph, GraphConfigError, merge_relation_layers
from .groups import (
    GroupBinding,
    GroupBindingError,
    GroupResolver,
    GroupScopeError,
    normalize_group_bindings,
    normalize_group_scopes,
)
from .models import (
    BotNode,
    InteractionEnvelope,
    Relation,
    is_placeholder_account_id,
    usable_account_id,
)
from .policy import InteractionGuard, PolicyDecision
from .persona import (
    MAX_PERSONA_PROMPT_CHARS,
    PersonaProfileError,
    normalize_persona_profiles,
    persona_profiles_for_group,
    resolve_persona_prompt,
)
from .persona_adapter import (
    PERSONA_ADAPT_SYSTEM_PROMPT,
    PersonaAdaptError,
    PersonaAdaptResult,
    apply_persona_adapt_response,
    build_persona_adapt_prompt,
)
from .protocol import ProtocolCodec, ProtocolError
from .relation_extractor import (
    RelationshipExtraction,
    RelationshipExtractionError,
    build_relationship_extraction_prompt,
    explicit_relationship_payload,
    hash_system_prompt,
    parse_relationship_extraction,
)
from .storage import InteractionStore
from .social import (
    ObserverDecision,
    RelationshipDelta,
    RelationshipState,
    SocialStateError,
    context_digest,
    effective_relation,
    parse_observer_decision,
    parse_relationship_delta,
    select_observer,
)

__all__ = [
    "BotGraph",
    "BotNode",
    "DeliveryPlan",
    "GraphConfigError",
    "GroupBinding",
    "GroupBindingError",
    "GroupResolver",
    "GroupScopeError",
    "InteractionEnvelope",
    "InteractionGuard",
    "InteractionStore",
    "is_placeholder_account_id",
    "PolicyDecision",
    "MAX_PERSONA_PROMPT_CHARS",
    "PersonaProfileError",
    "PERSONA_ADAPT_SYSTEM_PROMPT",
    "PersonaAdaptError",
    "PersonaAdaptResult",
    "apply_persona_adapt_response",
    "build_persona_adapt_prompt",
    "normalize_persona_profiles",
    "persona_profiles_for_group",
    "resolve_persona_prompt",
    "ProtocolCodec",
    "ProtocolError",
    "Relation",
    "ObserverDecision",
    "RelationshipDelta",
    "RelationshipState",
    "SocialStateError",
    "RelationshipExtraction",
    "RelationshipExtractionError",
    "RelationshipEditorError",
    "AUTOFILL_SYSTEM_PROMPT",
    "AutofillError",
    "AutofillResult",
    "apply_autofill_response",
    "build_autofill_prompt",
    "node_to_config",
    "build_relationship_extraction_prompt",
    "build_observation_delivery",
    "build_reply_delivery",
    "build_request_delivery",
    "explicit_relationship_payload",
    "context_digest",
    "effective_relation",
    "hash_system_prompt",
    "merge_relation_layers",
    "normalize_relation_entries",
    "normalize_node_entries",
    "normalize_group_bindings",
    "normalize_group_scopes",
    "parse_relationship_extraction",
    "parse_observer_decision",
    "parse_relationship_delta",
    "select_observer",
    "usable_account_id",
    "relation_to_config",
    "relationship_editor_payload",
]
