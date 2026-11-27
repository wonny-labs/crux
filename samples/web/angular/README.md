# Angular example

This example shows that a product can use Angular with Crux. It holds sign-in, the forced password change, home, a configuration screen, network settings and restart, uses the types generated from
the [management API specification](../../../web/api/openapi.yaml), and passes the same browser cases as the
[Preact example](../preact) on those screens. The [configuration flow](../../../docs/web-config-flow.md) describes the configuration screen, and
[the advanced flows](../../../docs/web-advanced-flows.md) describe the last two. Crux ships no Angular components. A product may copy or adapt
this example, but Crux does not maintain it as a starting template. The product owns its application UI.

The flows and the evidence state of both examples are in the [web guide](../../../web/README.md#flows).

| Topic | How it is set here |
| --- | --- |
| Routing | `withHashLocation`, so the server sees only the root path and the assets |
| CSRF | `HttpClient`'s default names, `XSRF-TOKEN` and `X-XSRF-TOKEN`, which the API uses. Nothing is configured. |
| Attempt poll | `X-Crux-Request: 1`, sent by `src/app/api.ts` |
| Logout | `responseType: 'text'`, because its `200` has an empty body |
| Change detection | Zoneless, so `zone.js` is not a dependency |
| Build | `@angular/build`, with critical CSS inlining and subresource integrity off, because both would need more from the policy |

## Inline style setting

**This example needs the inline style setting.** Angular inserts component styles into the page at run time, so a policy
without `'unsafe-inline'` in `style-src` blocks them. The composition that serves this example must choose:

```text
default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'
```

Scripts stay `'self'`, and `frame-ancestors 'none'` stays. The setting weakens only style injection, which can still restyle
a page to mislead a user, and a project should record that it chose this. The Preact example runs under the strict
setting. The measured effect is in the
[implementation design](../../../docs/plans/web-frontend-implementation.md#angular-comparison).

## Build and test

Use the Node.js version in `package.json`.

```sh
npm ci
npm run build
cd ../../../web
npm ci
npm run test:angular
```

The build writes `dist`, which the mock serves. Run `node tools/compare.ts` in `web` for the size table, after
`npm run build` and a build of `e2e/fixtures/two-screens.tsx` there.

## Limits

- It retries a held route (`409`) and nothing else by itself. A `503` is shown to the person with its wait, where the Preact example's client also retries one short `503` once.
- Its configuration screen edits parameters one at a time and has no sensitive-parameter write, as the Preact example.
- Sign-in always returns to home, so a link to a screen that is opened first does not survive it. The Preact example keeps it.
- Network settings and restart use the same words and the same checks as the Preact example (`src/app/texts.ts` holds the words, and the address checks are the client's own `checkIpv4Settings`).
- A login followed by a `401` on the current user returns to sign-in with no message.
