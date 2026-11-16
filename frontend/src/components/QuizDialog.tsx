import { ArrowRight, Check, CheckCheck } from 'lucide-react';
import { useState } from 'react';
import type { Quiz } from '../types';
import { ErrorText, Modal } from '../ui';

export function QuizDialog({
  quiz,
  working,
  close,
  submit,
}: {
  quiz: Quiz;
  working: boolean;
  close: () => void;
  submit: (answers: number[]) => Promise<void>;
}) {
  const [answers, setAnswers] = useState(quiz.answers || [-1, -1, -1]),
    [error, setError] = useState('');
  return (
    <Modal
      title={
        quiz.submitted
          ? quiz.score === 3
            ? 'Кажется, стало понятнее.'
            : 'Есть что разобрать вместе.'
          : 'Короткая проверка'
      }
      close={close}
    >
      <div className="quiz-intro">
        <span className="mono">
          {quiz.topic} /{' '}
          {quiz.stage === 'pre'
            ? 'ДО ВСТРЕЧИ'
            : quiz.stage === 'post'
              ? 'ПОСЛЕ ВСТРЕЧИ'
              : 'ПРАКТИКА'}
        </span>
        {quiz.submitted ? (
          <strong className="quiz-score">
            {quiz.score}
            <small>/ 3</small>
          </strong>
        ) : (
          <p>Три вопроса, чтобы увидеть, что уже понятно и о чём стоит спросить.</p>
        )}
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError('');
          try {
            await submit(answers);
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        {quiz.questions.map((q, i) => (
          <fieldset className="question" key={q.id}>
            <legend>
              <span>0{i + 1}</span>
              {q.text}
            </legend>
            {q.options.map((option, j) => (
              <label
                className={
                  'answer-option ' +
                  (answers[i] === j ? 'selected' : '') +
                  (quiz.submitted && quiz.feedback?.[i].correct === j ? ' correct' : '')
                }
                key={j}
              >
                <input
                  type="radio"
                  name={'question-' + i}
                  value={j}
                  checked={answers[i] === j}
                  disabled={quiz.submitted}
                  onChange={() => setAnswers(answers.map((a, k) => (k === i ? j : a)))}
                />
                <span>{option}</span>
                {quiz.submitted && quiz.feedback?.[i].correct === j && <Check size={15} />}
              </label>
            ))}
            {quiz.submitted && <p className="explanation">{quiz.feedback?.[i].explanation}</p>}
          </fieldset>
        ))}
        <ErrorText message={error} />
        {quiz.submitted ? (
          <>
            <p className="micro">
              Результат трёх вопросов показывает отдельные навыки. За успешный этап темы XP
              начисляется один раз.
            </p>
            <button type="button" className="button button-dark full" onClick={close}>
              Продолжить <ArrowRight size={17} />
            </button>
          </>
        ) : (
          <button
            className="button button-primary full"
            disabled={working || answers.some((a) => a < 0)}
          >
            Проверить ответы <CheckCheck size={17} />
          </button>
        )}
      </form>
    </Modal>
  );
}
