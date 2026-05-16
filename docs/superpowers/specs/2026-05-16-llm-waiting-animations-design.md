# LLM Waiting Animations Design

## Goal

Add visible, accessible animation to every user-facing place that waits for an LLM or AI job result.

## Scope

- Open-book submission while the blueprint request is being sent.
- Blueprint pending and running states while polling for AI output.
- Blueprint retry, revise, and accept actions while the request is pending.
- Chapter run and repair flows while the action request is pending, plus chapter running state while polling.
- Book workspace current-chapter and batch-production AI actions while pending.
- Canon proposal revision creation and running revision preview states.
- Quality center deconstruction and snapshot actions while pending.
- Provider configuration validation while testing LLM and optional embedding connections.

Non-LLM operations such as import, update checks, and export links stay unchanged.

## Design

Use a shared `AiWaitingIndicator` component with three parts: a compact pulse mark, a thin scanning rail, and clear status copy. The component should work inside existing workbench panels and setup messages without changing information architecture.

Buttons that trigger AI work use an inline compact waiting label. The button keeps its existing text intent while adding a pulse mark, so disabled states remain readable and do not shift layout.

The visual style stays calm and operational: warm brown action color, green supporting accent, low-opacity motion, no decorative full-screen overlays. Animations respect `prefers-reduced-motion` by falling back to static emphasis.

## Testing

Add focused React tests that assert the waiting indicators are present for representative AI states:

- Open book submit pending.
- Blueprint running state and pending action.
- Chapter running state and repair action.
- Workspace chapter production action.
- Canon running revision and revise action.
- Provider config validation pending.
- Quality center AI action pending.

