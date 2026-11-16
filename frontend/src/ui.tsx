import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, Check, LoaderCircle, X } from 'lucide-react';
export function Logo() {
  return (
    <span className="wordmark">
      <span className="brand-mark" aria-hidden="true">
        ✳
      </span>
      studymate<span className="brand-period">.</span>
    </span>
  );
}
export function Avatar({
  name,
  id = 0,
  large = false,
}: {
  name: string;
  id?: number;
  large?: boolean;
}) {
  return (
    <span
      className={'portrait portrait-' + (id % 5) + (large ? ' portrait-large' : '')}
      aria-hidden="true"
    >
      <span>{name.slice(0, 1)}</span>
      <i>✳</i>
    </span>
  );
}
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={'badge badge-' + tone}>{children}</span>;
}
export function ErrorText({ message, id }: { message: string; id?: string }) {
  return message ? (
    <p className="field-error" role="alert" id={id}>
      {message}
    </p>
  ) : null;
}
export function Empty({
  title,
  text,
  children,
}: {
  title: string;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="editorial-symbol">↗</span>
      <h2>{title}</h2>
      <p>{text}</p>
      {children}
    </div>
  );
}
export function Busy() {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={21} />
      <span>Один момент…</span>
    </div>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    const el = ref.current;
    const opener = document.activeElement as HTMLElement | null;
    el?.showModal();
    const cancel = (e: Event) => {
      e.preventDefault();
      closeRef.current();
    };
    el?.addEventListener('cancel', cancel);
    return () => {
      el?.removeEventListener('cancel', cancel);
      el?.close();
      if (opener && document.contains(opener)) opener.focus();
    };
  }, []);
  return (
    <dialog
      className="modal"
      ref={ref}
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-body">
        <div className="modal-title">
          <h2>{title}</h2>
          <button className="icon-button" onClick={close} aria-label="Закрыть">
            <X size={21} />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function Primary({
  children,
  onClick,
  disabled = false,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  return (
    <button className="button button-primary" type={type} onClick={onClick} disabled={disabled}>
      {children}
      <ArrowUpRight size={17} />
    </button>
  );
}
export function CheckText({ children }: { children: ReactNode }) {
  return (
    <span className="check-text">
      <Check size={14} />
      {children}
    </span>
  );
}
