(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const { Card, CardHeader, CardTitle, CardContent } = SDK.components;
  const SNAPSHOT_URL = "/api/plugins/hermes-factory/snapshot";

  function FactoryPage() {
    const [state, setState] = React.useState({ loading: true, data: null, error: null });

    React.useEffect(function () {
      let active = true;
      SDK.fetchJSON(SNAPSHOT_URL)
        .then(function (data) {
          if (active) setState({ loading: false, data: data, error: null });
        })
        .catch(function (error) {
          if (active) {
            setState({
              loading: false,
              data: null,
              error: error instanceof Error ? error.message : String(error),
            });
          }
        });
      return function () { active = false; };
    }, []);

    let body;
    if (state.loading) {
      body = React.createElement("p", { className: "text-sm text-muted-foreground" }, "Loading Factory truth…");
    } else if (state.error) {
      body = React.createElement("p", { className: "text-sm text-destructive" }, state.error);
    } else {
      body = React.createElement(
        "pre",
        { className: "overflow-auto text-xs whitespace-pre-wrap" },
        JSON.stringify(state.data, null, 2),
      );
    }

    return React.createElement(
      Card,
      null,
      React.createElement(
        CardHeader,
        null,
        React.createElement(CardTitle, null, "Hermes Software Factory"),
      ),
      React.createElement(CardContent, null, body),
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-factory", FactoryPage);
})();
