interface AsyncMessageProps {
  error?: string | null;
  loading?: boolean;
}

export function AsyncMessage({ error, loading }: AsyncMessageProps) {
  if (loading) {
    return <p className="async-message async-message--loading">Loading…</p>;
  }
  if (error) {
    return (
      <p className="async-message async-message--error" role="alert">
        {error}
      </p>
    );
  }
  return null;
}
