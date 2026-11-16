"""Local website notifications. No external messaging service is required."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from .events import queue_event
from .models import Booking, Notification, SessionToken, Slot
from .service import expire_pending, now


def deliver_notifications(database):
    with database.transaction() as session:
        expire_pending(session)
        from .groups import cancel_underfilled

        cancel_underfilled(session)
        for row in session.scalars(
            select(Notification).where(
                Notification.status.in_(["pending", "sending", "uncertain"]),
                Notification.due_at <= now(),
            )
        ):
            booking = session.get(Booking, row.booking_id) if row.booking_id else None
            stale = row.kind == "new_booking" and booking and booking.status != "pending"
            if row.kind == "reminder" and booking:
                stale = (
                    booking.status != "confirmed"
                    or session.get(Slot, booking.slot_id).ends_at <= now()
                    # The lesson was moved: this reminder belongs to the old slot.
                    or (row.slot_id is not None and row.slot_id != booking.slot_id)
                )
            row.status = "skipped" if stale else "in_app"
            row.sent_at = now()
            if not stale:  # e.g. a reminder that just became due
                queue_event(session, "notification", row.id, [row.user_id])
        for token in session.scalars(select(SessionToken).where(SessionToken.expires_at < now())):
            session.delete(token)


async def outbox_tick(database):
    await asyncio.to_thread(deliver_notifications, database)


async def run_workers(database):
    while True:
        try:
            await outbox_tick(database)
        except OperationalError:
            logging.getLogger("studymate").warning("Database busy; inbox will retry")
        await asyncio.sleep(2)
