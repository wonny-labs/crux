# Preact example

The reference browser front end for the [management API](../../../web/api/openapi.yaml): sign-in, the forced password
change, home, configuration, network settings and reboot. It runs under the strict content security policy, with no
inline styles. A product may copy it, but Crux does not maintain it as a starting template. The product owns its
application UI. The [configuration flow](../../../docs/web-config-flow.md) and
[the advanced flows](../../../docs/web-advanced-flows.md) describe the screens, and the packaging budget is
[`budget.json`](budget.json).

## Build and test

The example has no `package.json` of its own. It takes `preact` and the build, client, mock and browser tests from
[`web/`](../../../web/README.md), so everything runs from there. Use the Node.js version in `web/package.json`, and
Chrome from the machine.

```sh
cd web
npm ci
npm run build          # writes samples/web/preact/dist, and fails over the budget
npm run test:browser   # builds again, then runs the browser tests against the mock
```

In the Linux Dev Container, from the repository root, `scripts/test-native-composition.sh e2e-mbed` builds both
examples, packages them into a `native_sim` image and runs the shared and real-server browser cases over HTTPS.

## See also

- [Web guide](../../../web/README.md): the commands, the mock server and how a product builds its own interface.
- [Angular example](../angular/README.md): the same screens in another framework, for comparison.
