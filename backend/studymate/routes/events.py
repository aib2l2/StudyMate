"""Live update stream (Server-Sent Events) with single-use tickets."""

import asyncio
import json

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse

from ..deps import bearer_hash, write_user
from ..events import CLOSE
from ..models import SessionToken, User
from ..schemas import TicketOut
from ..service import fail, now
from . import Router

router = Router(prefix="/api/events", tags=["events"])


@router.post("/ticket", response_model=TicketOut)
def ticket(
    request: Request,
    authorization: str | None = Header(default=None),
    user: User = Depends(write_user),
):
    return {"ticket": request.app.state.tickets.issue(user.id, bearer_hash(authorization))}


def _token_valid(db, token_hash: str) -> bool:
    # A short read of its own: the stream never keeps a transaction open.
    with db.read() as s:
        token = s.get(SessionToken, token_hash)
        return token is not None and token.expires_at > now()


@router.get("", include_in_schema=False)
async def stream(ticket: str, request: Request):
    state = request.app.state
    redeemed = state.tickets.redeem(ticket)
    if redeemed is None:
        fail(401, "Ссылка на поток устарела, запросите новую")
    user_id, token_hash = redeemed
    if not await asyncio.to_thread(_token_valid, state.db, token_hash):
        fail(401, "Войдите заново: сессия завершилась")
    bus = state.db.bus
    sub = bus.subscribe(user_id, token_hash)
    if sub is None:
        fail(429, "Открыто слишком много вкладок StudyMate")
    heartbeat = state.heartbeat_seconds

    async def events():
        ended = 'event: session_ended\ndata: {"type":"session_ended"}\n\n'
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(sub.queue.get(), heartbeat)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    if not await asyncio.to_thread(_token_valid, state.db, token_hash):
                        yield ended
                        return
                    yield ": ping\n\n"
                    continue
                if item is CLOSE:
                    if sub.closed and not await asyncio.to_thread(
                        _token_valid, state.db, token_hash
                    ):
                        yield ended
                    return
                yield f"id: {bus.next_id()}\ndata: {json.dumps(item)}\n\n"
        finally:
            bus.unsubscribe(sub)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
