"""Pre/post-lesson and practice quizzes."""

from fastapi import Depends
from sqlalchemy.orm import Session

from ..deps import read_session, read_user, write_session, write_user
from ..models import QuizAttempt, User
from ..quizzes import attempt_json, start_attempt, submit_attempt
from ..schemas import AnswersInput, QuizInput, QuizOut
from ..service import fail, get
from . import Router

router = Router(prefix="/api/quizzes", tags=["quizzes"])


@router.post("", response_model=QuizOut)
def quiz_start(
    data: QuizInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    return start_attempt(s, user, data.topic_id, data.stage, data.booking_id)


@router.get("/{attempt_id}", response_model=QuizOut)
def quiz_get(attempt_id: str, user: User = Depends(read_user), s: Session = Depends(read_session)):
    attempt = get(s, QuizAttempt, attempt_id)
    if attempt.user_id != user.id:
        fail(403, "Это попытка другого пользователя")
    return attempt_json(s, attempt)


@router.post("/{attempt_id}/submit", response_model=QuizOut)
def quiz_submit(
    attempt_id: str,
    data: AnswersInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    return submit_attempt(s, user, attempt_id, data.answers)
