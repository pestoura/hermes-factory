(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;

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

    return React.createElement(
      "section",
      { className: "flex h-full flex-col gap-4 overflow-auto p-6" },
      React.createElement(
        "header",
        null,
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
      ),
      React.createElement(
        "pre",
        { className: "overflow-auto whitespace-pre-wrap text-xs" },
        JSON.stringify(state.data, null, 2),
      ),
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-factory", FactoryPage);
})();
