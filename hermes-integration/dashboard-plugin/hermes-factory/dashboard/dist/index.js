(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;

  const FACTORY_SECTIONS = [
    { label: "Portfolio / Projects", keys: ["projects"] },
    {
      label: "Epics / Work Packages / Requirements",
      keys: ["epics", "work_packages", "requirements"],
    },
    { label: "Kanban / Execution", keys: ["kanban"] },
    { label: "Profiles / Skills", keys: ["agent_evals", "skill_evals"] },
    { label: "SCM / CI", keys: ["scm"] },
    { label: "JDS Gates", keys: ["jds_gates"] },
    { label: "UAT", keys: ["uat"] },
    { label: "Findings / Rework", keys: ["corrective_action"] },
    { label: "HITL", keys: ["hitl"] },
    { label: "Runtime", keys: ["runtime"] },
    { label: "Evidence Freshness", keys: ["evidence"] },
    { label: "Acceptance / Release", keys: ["acceptance"] },
  ];

  function sectionRows(data, keys) {
    return keys.flatMap((key) => {
      const rows = Array.isArray(data[key]) ? data[key] : [];
      return rows.map((row) => ({ source: key, record: row }));
    });
  }

  function renderFactorySection(section, data) {
    const rows = sectionRows(data, section.keys);
    return React.createElement(
      "section",
      {
        key: section.label,
        className: "rounded-lg border border-border bg-card p-4",
      },
      React.createElement(
        "div",
        { className: "mb-3 flex items-center justify-between gap-3" },
        React.createElement(
          "h2",
          { className: "text-sm font-semibold" },
          section.label,
        ),
        React.createElement(
          "span",
          { className: "text-xs text-muted-foreground" },
          String(rows.length),
        ),
      ),
      rows.length === 0
        ? React.createElement(
            "p",
            { className: "text-xs text-muted-foreground" },
            "No canonical records",
          )
        : React.createElement(
            "pre",
            { className: "overflow-auto whitespace-pre-wrap text-xs" },
            JSON.stringify(rows, null, 2),
          ),
    );
  }

  function FactoryPage() {
    const [state, setState] = React.useState({
      loading: true,
      data: null,
      error: null,
    });

    React.useEffect(() => {
      let active = true;

      SDK.fetchJSON("/api/plugins/hermes-factory/snapshot")
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
    }, []);

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

    const data = state.data || {};
    const candidate = data.candidate || "portfolio / unbound candidate view";

    return React.createElement(
      "main",
      { className: "flex h-full flex-col gap-4 overflow-auto p-6" },
      React.createElement(
        "header",
        { className: "space-y-1" },
        React.createElement(
          "h1",
          { className: "text-lg font-semibold" },
          "Hermes Software Factory",
        ),
        React.createElement(
          "p",
          { className: "text-sm text-muted-foreground" },
          "Canonical Factory state and evidence (read-only)",
        ),
        React.createElement(
          "p",
          { className: "font-mono text-xs text-muted-foreground" },
          `Candidate: ${candidate}`,
        ),
      ),
      React.createElement(
        "div",
        { className: "grid gap-4 xl:grid-cols-2" },
        ...FACTORY_SECTIONS.map((section) => renderFactorySection(section, data)),
      ),
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-factory", FactoryPage);
})();
