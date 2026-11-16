import { ArrowUpRight } from 'lucide-react';
import { useRef, useState } from 'react';
import { dateTime, money } from '../api';
import type { Filters, Mentor } from '../types';
import { Avatar, ErrorText, Modal } from '../ui';

export function BookingDialog({
  mentor,
  slotId,
  topicId,
  filters,
  close,
  working,
  submit,
}: {
  mentor: Mentor;
  slotId: number;
  topicId: number;
  filters: Filters;
  close: () => void;
  working: boolean;
  submit: (body: unknown) => Promise<void>;
}) {
  const [description, setDescription] = useState(''),
    [error, setError] = useState('');
  const key = useRef(crypto.randomUUID());
  const slot = mentor.slots.find((s) => s.id === slotId)!;
  const group = (slot.capacity ?? 1) > 1;
  return (
    <Modal title="На каком шаге застрял?" close={close}>
      <div className="booking-recap">
        <Avatar name={mentor.name} id={mentor.id} />
        <div>
          <strong>{mentor.name}</strong>
          <small>{dateTime(slot.starts_at)} / 30 минут</small>
        </div>
        <strong>{money(group ? (slot.price ?? 0) : mentor.price)}</strong>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError('');
          try {
            await submit({
              ...filters,
              slot_id: slotId,
              // A group lesson is about its own topic and has a fixed format.
              topic_id: group ? slot.topic_id : topicId,
              ...(group ? { format: slot.format } : {}),
              description,
              request_key: key.current,
            });
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <label className="field">
          Что хотелось бы понять к концу встречи?
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            minLength={3}
            maxLength={1500}
            required
            rows={4}
            placeholder="Например: хочу понять, почему LEFT JOIN возвращает больше строк, чем INNER JOIN."
          />
        </label>
        <ErrorText message={error} />
        <button className="button button-primary full" disabled={working}>
          {group ? 'Записаться в группу' : 'Отправить заявку'} <ArrowUpRight size={17} />
        </button>
        <p className="micro">
          {group
            ? `Место подтверждается сразу: занято ${slot.taken ?? 0} из ${slot.capacity}. Ссылка или аудитория уже указаны ментором.`
            : 'Ментор ответит в течение 15 минут.'}{' '}
          Стоимость фиксируется в заявке. Оплата в этой версии демонстрационная.
        </p>
      </form>
    </Modal>
  );
}
