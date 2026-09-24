/**
 * Normalizer - Maps platform-native shapes to unified domain model
 * Uses CLOSED transform set only (no arbitrary expressions)
 */

// ──────────────────────────────────────────────────────────────
// CLOSED TRANSFORM SET
// ──────────────────────────────────────────────────────────────
const TRANSFORMS = {
  identity: (v) => v,
  toString: (v) => String(v),
  toNumber: (v) => Number(v),
  toBoolean: (v) => Boolean(v),
  iso8601ToEpochMs: (v) => v ? Date.parse(v) : null,
  epochSecToEpochMs: (v) => v * 1000,
  snowflakeToEpochMs: (v) => {
    if (!v) return null;
    const big = BigInt(v);
    return Number((big >> 22n) + 1420070400000n);
  },
  mapEach: (arr, entity, mappings) => {
    if (!Array.isArray(arr)) return [];
    return arr.map(item => normalizeEntity(entity, item, mappings, 'one'));
  },
  pick: (obj, keys) => {
    if (!obj) return {};
    const result = {};
    for (const k of keys) result[k] = obj[k];
    return result;
  },
  coalesce: (...vals) => vals.find(v => v != null),
  constant: (v, spec) => spec?.value,
  enumMap: (v, spec) => spec?.table?.[v] ?? spec?.fallback ?? 'unknown',
};

function applyTransform(value, transformSpec, mappings) {
  if (!transformSpec) return value;

  const { transform, ...params } = transformSpec;
  const fn = TRANSFORMS[transform];
  if (!fn) throw new Error(`Unknown transform: ${transform}`);

  switch (transform) {
    case 'mapEach':
      return fn(value, params.entity, mappings);
    case 'pick':
      return fn(value, params.keys);
    case 'coalesce':
      return fn(...params.args);
    case 'constant':
      return fn(value, params);
    case 'enumMap':
      return fn(value, params);
    default:
      return fn(value);
  }
}

// ──────────────────────────────────────────────────────────────
// PATH RESOLUTION (structural, no eval)
// ──────────────────────────────────────────────────────────────
const FORBIDDEN_SEGMENTS = new Set(['__proto__', 'constructor', 'prototype']);

function resolvePath(obj, path) {
  if (!path || !Array.isArray(path)) return obj;
  let current = obj;
  for (const segment of path) {
    if (typeof segment !== 'string') throw new Error('Path segment must be string');
    if (FORBIDDEN_SEGMENTS.has(segment)) throw new Error(`Forbidden segment: ${segment}`);
    if (current == null) return undefined;
    current = current[segment];
  }
  return current;
}

// ──────────────────────────────────────────────────────────────
// ENTITY NORMALIZATION
// ──────────────────────────────────────────────────────────────
export function normalizeEntity(entityName, raw, mapping, cardinality) {
  if (!raw) return cardinality === 'many' ? [] : null;
  if (cardinality === 'many' && Array.isArray(raw)) {
    return raw.map(item => normalizeEntity(entityName, item, mapping, 'one')).filter(Boolean);
  }

  const result = { platform: '', externalId: '', raw: raw };

  if (!mapping) return result;

  for (const [targetField, spec] of Object.entries(mapping)) {
    let value;

    if (spec.from) {
      const sourcePath = spec.from.startsWith('param:') ? null : spec.from;
      value = sourcePath ? resolvePath(raw, sourcePath.split('.')) : raw;
    } else if (spec.transform) {
      value = applyTransform(raw, spec, mapping);
    } else {
      value = raw;
    }

    if (value !== undefined && value !== null) {
      result[targetField] = applyTransform(value, spec, mapping);
    } else if (!spec.nullable) {
      result[targetField] = undefined;
    }
  }

  return result;
}

export function normalize(capability, raw, fingerprint) {
  // Determine entity from capability
  const capDef = fingerprint.capabilities?.[capability];
  if (!capDef?.returns?.entity) return raw;

  return normalizeEntity(
    capDef.returns.entity,
    raw,
    fingerprint.entities?.[capDef.returns.entity]?.mapping,
    capDef.returns.cardinality
  );
}

// ──────────────────────────────────────────────────────────────
// UNIFIED DOMAIN MODEL HELPERS
// ──────────────────────────────────────────────────────────────
export function createEntityId(prefix, externalId) {
  return `${prefix}_${externalId}`;
}

export function createMessageEntity(raw, mapping, platform) {
  return normalizeEntity('Message', raw, mapping, 'one');
}

export function createConversationEntity(raw, mapping, platform) {
  return normalizeEntity('Conversation', raw, mapping, 'one');
}

export function createContactEntity(raw, mapping, platform) {
  return normalizeEntity('Contact', raw, mapping, 'one');
}

export function createAccountEntity(raw, mapping, platform) {
  return normalizeEntity('Account', raw, mapping, 'one');
}