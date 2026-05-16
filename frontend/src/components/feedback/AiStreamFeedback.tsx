type AiStreamFeedbackProps = {
  snippets: string[];
};

export function AiStreamFeedback({ snippets }: AiStreamFeedbackProps) {
  const active = snippets.length > 0;
  return (
    <div
      aria-hidden={active ? undefined : true}
      aria-live={active ? "polite" : undefined}
      className={active ? "ai-stream-feedback" : "ai-stream-feedback is-idle"}
      role={active ? "status" : undefined}
    >
      {snippets.map((snippet, index) => (
        <span key={`${snippet}-${index}`}>{snippet}</span>
      ))}
    </div>
  );
}
