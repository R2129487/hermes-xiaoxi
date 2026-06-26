from .health import router as health_router
from .auth import router as auth_router
from .agents import router as agents_router
from .messages import router as messages_router
from .capabilities import router as capabilities_router
from .tasks import router as tasks_router
from .decisions import router as decisions_router
from .audit import router as audit_router
from .tokens import router as tokens_router
from .permissions import router as permissions_router
from .stats import router as stats_router
from .brain import router as brain_router

__all__ = [
    "health_router",
    "auth_router",
    "agents_router",
    "messages_router",
    "capabilities_router",
    "tasks_router",
    "decisions_router",
    "audit_router",
    "tokens_router",
    "permissions_router",
    "stats_router",
    "brain_router",
]
