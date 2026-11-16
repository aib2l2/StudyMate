import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
class ErrorBoundary extends React.Component<
  {
    children: React.ReactNode;
  },
  {
    failed: boolean;
  }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="boot-page">
        <h1>Обновим страницу?</h1>
        <p>Интерфейс не смог завершить действие. Сохранённые записи остаются в базе.</p>
        <button className="button button-primary" onClick={() => location.reload()}>
          Открыть снова
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
