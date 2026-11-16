# Host protocol

The host protocol lets clients discover hosts, find notebooks, edit documents,
and follow execution through HTTP requests and event streams.

- [Specification](spec.md) — the model and behavior a host implements.
- [OpenAPI](#get-the-openapi-document) — HTTP routes and wire schemas, printed on demand.
- [TypeScript client](../../packages/client/README.md) — connect to a host.
- [Effect contracts](../../packages/host-protocol/README.md) — author the definitions.
- [Examples](fixtures/README.md), [conformance tests](conformance/README.md),
  and [experimental features](experimental/README.md).

## Change a contract

Edit the definitions in [`packages/host-protocol`](../../packages/host-protocol/README.md).
The Python models and TypeScript bindings are generated from them and checked
in. They should not be edited by hand.

Keep the [specification](spec.md), implementation, and relevant fixtures or
tests in step with the change. After the repository
[development setup](../../CONTRIBUTING.md#setup), run from the root:

```sh
make host-protocol-codegen
pnpm --dir packages/client codegen

make host-protocol-check
pnpm --dir packages/client codegen:check
```

The first command generates Python and the second generates TypeScript. The
checks verify those outputs and run the portable fixtures.

Also run the [package checks](../../packages/host-protocol/README.md#working-on-the-package)
and tests for the implementation you changed. To check a host over a real
connection, use the [live conformance suite](conformance/README.md#check-a-running-host).

## Get the OpenAPI document

No OpenAPI file is checked in. The package prints the document as JSON, and
the generators above read it from a pipe.

```sh
node packages/host-protocol/scripts/openapi.ts                 # the stable protocol
node packages/host-protocol/scripts/openapi.ts --experimental  # with experimental features
```

The script needs Node and the package's one dependency, which
`pnpm install --filter @marimo-team/host-protocol --prod` installs.

To build on the stable protocol in another language, save the first output and
point an OpenAPI generator at it. marimo's own bindings use the second, which
adds every [experimental feature](experimental/README.md).
