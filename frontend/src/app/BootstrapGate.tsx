import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { BootstrapPayload } from "@/lib/types";
import { SetupOnlyShell } from "@/components/layout/SetupOnlyShell";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";

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
    <main className="workbench-placeholder" aria-labelledby="workbench-title">
      <section className="workbench-placeholder__card">
        <p className="eyebrow">MyNovel</p>
        <h1 id="workbench-title">工作台准备中</h1>
        <p className="lede">模型配置已完成，完整工作台将在后续任务接入。</p>
      </section>
    </main>
  );
}

function fetchAppBootstrap(): Promise<BootstrapPayload> {
  return getJson<BootstrapPayload>("/api/app/bootstrap");
}
