Brand Base64String through codegen

`bytes` fields in msgspec already emit `contentEncoding: base64` in the
schema, but `openapi-typescript` drops that and generates plain `string`.
This adds a named `Base64String` schema and replaces the inline
occurrences with `$ref` pointers, then brands it as
`TypedString<"Base64String">` in the codegen output. The frontend type
derives from the schema and the `@ts-expect-error` + `as Base64String`
cast on `notification.buffers` are no longer needed.
