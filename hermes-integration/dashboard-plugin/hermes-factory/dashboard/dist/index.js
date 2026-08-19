import React, { useEffect, useState } from "react";
import { ROUTES_AREA, SIDEBAR_NAV_AREA } from "@hermes/plugin-sdk";

function FactoryPage({ loadSnapshot }) {
  const [state, setState] = useState({ loading: true, data: null, error: null });

  useEffect(() => {
    let active = true;

    loadSnapshot()
      .then((data) => {
        if (active) {
          setState({ loading: false, data, error: null });
        }
      })
      .catch((error) => {
        if (active) {
          setState({
            loading: false,
            data: null,
            error: error instanceof Error ? error.message : String(error),
          });
        }
      });

    return () => {
      active = false;
    };
  }, [loadSnapshot]);

  if (state.loading) {
    return React.createElement(
      "div",
      { className: "p-6 text-sm text-muted-foreground" },
      "Loading Factory truth…",
    );
  }

  if (state.error) {
    return React.createElement(
      "div",
      { className: "p-6 text-sm text-destructive" },
      state.error,
    );
  }

  return React.createElement(
    "section",
    { className: "flex h-full flex-col gap-4 overflow-auto p-6" },
    React.createElement(
      "header",
      null,
      React.createElement("h1", { className: "text-lg font-semibold" }, "Hermes Software Factory"),
      React.createElement(
        "p",
        { className: "text-sm text-muted-foreground" },
        "Canonical Factory state and evidence (read-only)",
      ),
    ),
    React.createElement(
      "pre",
      { className: "overflow-auto whitespace-pre-wrap text-xs" },
      JSON.stringify(state.data, null, 2),
    ),
  );
}

const plugin = {
  id: "hermes-factory",
  name: "Hermes Software Factory",
  defaultEnabled: true,
  register(ctx) {
    const loadSnapshot = () => ctx.rest("/snapshot");
    const renderFactory = () => React.createElement(FactoryPage, { loadSnapshot });

    ctx.register({
      id: "route",
      area: ROUTES_AREA,
      title: "Hermes Software Factory",
      data: { path: "/factory" },
      render: renderFactory,
    });

    ctx.register({
      id: "sidebar-nav",
      area: SIDEBAR_NAV_AREA,
      data: {
        codicon: "organization",
        label: "Factory",
        path: "/factory",
      },
    });
  },
};

export default plugin;
