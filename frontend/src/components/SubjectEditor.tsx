import { useState } from 'react';
import type { Subject } from '../types';
import { Badge } from '../ui';

export function SubjectEditor({
  subject,
  working,
  save,
}: {
  subject: Subject;
  working: boolean;
  save: (body: unknown) => Promise<void>;
}) {
  const [name, setName] = useState(subject.name);
  return (
    <form
      className="subject-editor"
      onSubmit={(e) => {
        e.preventDefault();
        void save({ name, active: subject.active });
      }}
    >
      <input
        aria-label={'Название предмета ' + subject.name}
        value={name}
        onChange={(e) => setName(e.target.value)}
        minLength={2}
        maxLength={100}
        required
      />
      <Badge>{subject.active ? 'В каталоге' : 'Отключён'}</Badge>
      <button className="button button-outline" disabled={working}>
        Сохранить
      </button>
      <button
        type="button"
        className="inline-link"
        disabled={working}
        onClick={() => void save({ name, active: !subject.active })}
      >
        {subject.active ? 'Отключить' : 'Включить'}
      </button>
    </form>
  );
}
