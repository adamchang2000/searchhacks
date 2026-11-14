# @searchhacks/optimizer-protocol

The HTTP protocol exported by `app/optimizer-server`. The Django/ninja API is the source
of truth, and this package is generated from it:

- `schema.json`: OpenAPI schema exported from the server
- `src/generated/api.ts`: TypeScript types generated from `schema.json`
- `src/client.ts`: typed client (`openapi-fetch`) used by the SDK, mock driver, and UI

Both generated files are checked in, so protocol changes show up in diffs and the TS
packages build without a Python env. Regenerate after changing any API schema:

```bash
make generate-api   # from repo root
```
