"""Pause between two emails to the same address (protects other people's inboxes).

The last send time is kept in the database (table email_throttle), so the pause
works with several server processes and survives a restart.
"""
from datetime import datetime, timedelta
from math import ceil

from sqlalchemy.exc import IntegrityError

from database import db
from database.models import EmailThrottle

COOLDOWN_SECONDS = 60


def claim_email_slot(email, cooldown=COOLDOWN_SECONDS):
    """Ask: may we email this address right now?

    Returns 0 if yes (and remembers the moment, so the next call has to wait),
    otherwise the number of seconds left to wait. Login links and sign-up
    confirmations share one pause, so switching forms does not help.
    """
    key = f"auth:{email.strip().lower()}"
    now = datetime.utcnow()

    # forget old records so the table does not grow forever
    EmailThrottle.query.filter(EmailThrottle.sent_at < now - timedelta(days=1)).delete()

    row = db.session.get(EmailThrottle, key)
    if row is not None:
        left = cooldown - (now - row.sent_at).total_seconds()
        if left > 0:
            db.session.rollback()
            return max(1, ceil(left))
        row.sent_at = now
    else:
        db.session.add(EmailThrottle(key=key, sent_at=now))

    try:
        db.session.commit()
    except IntegrityError:  # another request for the same address won the race
        db.session.rollback()
        return cooldown
    return 0
