import { Star } from 'lucide-react';
import { useState } from 'react';

/** Toggle for favorites; `aria-pressed` tells assistive tech the state. */
export function FavoriteButton({
  name,
  active,
  toggle,
}: {
  name: string;
  active: boolean;
  toggle: (next: boolean) => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      className={'favorite-button' + (active ? ' active' : '')}
      aria-pressed={active}
      aria-label={active ? `Убрать ${name} из избранного` : `Добавить ${name} в избранное`}
      title={active ? 'В избранном' : 'В избранное'}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await toggle(!active);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Star size={18} fill={active ? 'currentColor' : 'none'} />
    </button>
  );
}
