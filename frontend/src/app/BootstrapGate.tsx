import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { BootstrapPayload } from "@/lib/types";
import { AppShell } from "@/components/layout/AppShell";
import { SetupOnlyShell } from "@/components/layout/SetupOnlyShell";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";

type BootstrapGateProps = {
  bootstrap?: BootstrapPayload;
  fetchBootstrap?: () => Promise<BootstrapPayload>;
};

type BootstrapState =
  | { status: "loading"; payload: null; error: null }
  | { status: "ready"; payload: BootstrapPayload; error: null }
  | { status: "error"; payload: null; error: string };

export function BootstrapGate({
  bootstrap,
  fetchBootstrap = fetchAppBootstrap,
}: BootstrapGateProps) {
  const [state, setState] = useState<BootstrapState>(() =>
    bootstrap
      ? { status: "ready", payload: bootstrap, error: null }
      : { status: "loading", payload: null, error: null },
  );

  useEffect(() => {
    if (bootstrap) {
      setState({ status: "ready", payload: bootstrap, error: null });
      return;
    }

    let cancelled = false;
    fetchBootstrap()
      .then((payload) => {
        if (!cancelled) {
          setState({ status: "ready", payload, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            payload: null,
            error: error instanceof Error ? error.message : "启动信息加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [bootstrap, fetchBootstrap]);

  if (state.status === "loading") {
    return (
      <SetupOnlyShell>
        <div className="setup-status-card" role="status">
          正在加载启动信息...
        </div>
      </SetupOnlyShell>
    );
  }

  if (state.status === "error") {
    return (
      <SetupOnlyShell>
        <ProviderConfigPage bootstrapMessage={state.error} />
      </SetupOnlyShell>
    );
  }

  if (!state.payload.providerConfigured) {
    return (
      <SetupOnlyShell>
        <ProviderConfigPage bootstrapMessage={state.payload.message} />
      </SetupOnlyShell>
    );
  }

  return (
    <AppShell>
      <WorkbenchPage />
    </AppShell>
  );
}

function fetchAppBootstrap(): Promise<BootstrapPayload> {
  return getJson<BootstrapPayload>("/api/app/bootstrap");
}
