# Msgspec Migration: Serialization Differences and Caveats

## Overview
This document outlines the serialization differences between our previous `WebComponentEncoder` and the new `msgspec` encoder, along with important caveats to be mindful of during and after the migration.

## Key Serialization Differences

### 1. `datetime.timedelta`
**Previous (WebComponentEncoder):** Python string representation (e.g., `"1 day, 2:30:00"`)  
**New (msgspec):** ISO 8601 duration format (e.g., `"P1DT9000S"`)  

**Impact:** Frontend will receive different format. Need to add ISO 8601 duration parsing to frontend.  
**Migration Status:** Deferred to frontend update (TODO #14)

### 2. `bytes` / `bytearray` / `memoryview`
**Previous (WebComponentEncoder):** UTF-8/Latin-1 decoded string (e.g., `"hello"`)  
**New (msgspec):** Base64-encoded string (e.g., `"aGVsbG8="`)  

**Impact:** More robust handling of binary data, but frontend needs to decode base64 if displaying raw bytes.  
**Migration Status:** Accepted change - base64 is the standard for JSON binary data

### 3. Plain `Enum` (not `str, Enum` or `IntEnum`)
**Previous (WebComponentEncoder):** Enum name (e.g., `"RED"` for `Color.RED`)  
**New (msgspec):** Enum value (e.g., `"red"` for `Color.RED = "red"`)  

**Impact:** Only affects plain Enum classes. Does NOT affect:
- `str, Enum` types (like `CellChannel`) - both use value ✅
- `IntEnum` types (like `HTTPStatus`) - both use value ✅

**Migration Status:** No plain Enums found in serialized messages

## Types That Work Identically

The following types serialize identically between both encoders:
- All primitive types: `str`, `int`, `float`, `bool`, `None`
- Collections: `list`, `dict`, `set`, `frozenset`, `tuple`
- Datetime types: `datetime`, `date`, `time` (ISO format)
- `UUID` (string representation)
- `Decimal` (as number with `decimal_format='number'`)
- `range` (as list)
- `complex` (as string representation)
- Named tuples (as dict with field names)
- Dataclasses (as dict)
- Objects with `_mime_()` method (custom marimo protocol)
- NumPy types (when available)
- Pandas DataFrames/Series (when available)
- Polars DataFrames/Series (when available)

## Important Caveats

### 1. Native Type Handling
Msgspec handles many types natively (datetime, timedelta, UUID, Decimal, Enum, bytes). The `enc_hook` is ONLY called for types msgspec doesn't recognize. This means:
- We cannot override native type serialization via `enc_hook`
- Any customization requires preprocessing or frontend changes

### 2. Performance Considerations
- Msgspec is written in C and is significantly faster than pure Python
- The `enc_hook` is still Python, so custom type handling may be a bottleneck
- Reuse encoder instances when possible (`encoder` is module-level singleton)

### 3. Strict Type Validation
Unlike `json.dumps`, msgspec will be stricter about types during decoding:
- Better error messages for type mismatches
- Can validate against struct schemas
- May catch bugs that were previously silent

### 4. Future Frontend Updates Needed
- [ ] Add ISO 8601 duration parser for timedelta display
- [ ] Handle base64-encoded bytes if displayed directly
- [ ] Update any hardcoded expectations of enum names vs values

## Testing Checklist

Before completing migration:
- [x] Verify all message types serialize correctly
- [x] Test with NumPy/Pandas/Polars if available
- [x] Ensure WebSocket messages are received correctly
- [ ] Test edge cases with special characters, large data
- [ ] Verify no performance regressions
- [ ] Test that frontend handles all format changes

## Rollback Plan

If issues arise:
1. The `WebComponentEncoder` is preserved until migration is complete
2. Can temporarily add preprocessing for problematic types
3. Frontend can detect format and handle both old and new

## Benefits of Migration

1. **Performance:** Msgspec is 5-10x faster for encoding/decoding
2. **Type Safety:** Better validation and error messages
3. **Standards:** Uses standard formats (ISO 8601, base64) where applicable
4. **Maintenance:** Less custom code to maintain
5. **Memory:** More efficient memory usage with structs vs dataclasses