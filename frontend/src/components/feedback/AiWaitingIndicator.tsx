type AiWaitingIndicatorVariant = "panel" | "message" | "inline" | "hero";

type AiWaitingIndicatorProps = {
  className?: string;
  detail?: string;
  label: string;
  variant?: AiWaitingIndicatorVariant;
};

export function AiWaitingIndicator({
  className,
  detail,
  label,
  variant = "panel",
}: AiWaitingIndicatorProps) {
  const classes = ["ai-waiting", `ai-waiting--${variant}`, className].filter(Boolean).join(" ");
  const content = (
    <>
      <span className="ai-waiting__pulse" aria-hidden="true">
        <span />
      </span>
      <span className="ai-waiting__copy">
        <span className="ai-waiting__label">{label}</span>
        {detail ? <span className="ai-waiting__detail">{detail}</span> : null}
      </span>
      {variant !== "inline" ? (
        <span className="ai-waiting__rail" aria-hidden="true">
          <span />
        </span>
      ) : null}
    </>
  );

  if (variant === "inline") {
    return (
      <span className={classes} data-testid="ai-waiting-indicator">
        {content}
      </span>
    );
  }

  return (
    <div
      aria-label={label}
      aria-live="polite"
      className={classes}
      data-testid="ai-waiting-indicator"
      role="status"
    >
      {content}
    </div>
  );
}
