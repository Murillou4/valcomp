import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const sourceRoot = path.resolve(process.argv[2] ?? "");
const outputPath = path.resolve(process.argv[3] ?? "");

if (!sourceRoot || !outputPath) {
  throw new Error("Usage: node tools/export_catalog.mjs <valorant-api-types> <output.json>");
}

const require = createRequire(import.meta.url);
const { endpoints } = require(path.join(sourceRoot, "dist", "endpoints.js"));
const packageJson = JSON.parse(
  fs.readFileSync(path.join(sourceRoot, "package.json"), "utf8"),
);

function unwrap(schema) {
  let current = schema;
  let optional = false;
  let nullable = false;
  while (current?._def?.typeName === "ZodOptional" || current?._def?.typeName === "ZodNullable") {
    if (current._def.typeName === "ZodOptional") optional = true;
    if (current._def.typeName === "ZodNullable") nullable = true;
    current = current._def.innerType;
  }
  return { schema: current, optional, nullable };
}

function schemaInfo(input, depth = 0) {
  if (!input || depth > 12) return { type: "unknown" };
  const { schema, optional, nullable } = unwrap(input);
  const name = schema?._def?.typeName ?? "Unknown";
  const base = {
    type: name.replace(/^Zod/, "").toLowerCase(),
    optional,
    nullable,
    description: input.description ?? schema.description ?? "",
  };

  if (name === "ZodEnum") base.options = schema._def.values;
  if (name === "ZodLiteral") base.literal = schema._def.value;
  if (name === "ZodArray") base.items = schemaInfo(schema._def.type, depth + 1);
  if (name === "ZodUnion") base.options = schema._def.options.map((item) => schemaInfo(item, depth + 1));
  if (name === "ZodObject") {
    const shape = schema._def.shape();
    base.fields = Object.fromEntries(
      Object.entries(shape).map(([key, value]) => [key, schemaInfo(value, depth + 1)]),
    );
  }
  return base;
}

function exampleFor(input, fieldName = "", depth = 0) {
  if (!input || depth > 9) return null;
  const { schema, optional, nullable } = unwrap(input);
  if (optional) return undefined;
  if (nullable) return null;
  const name = schema?._def?.typeName;

  if (name === "ZodString") {
    const normalized = fieldName.toLowerCase();
    if (normalized.includes("uuid") || normalized.endsWith("id")) return `<${fieldName || "id"}>`;
    if (normalized.includes("message")) return "mensagem";
    if (normalized.includes("tag")) return "BR1";
    if (normalized.includes("name")) return "Nome";
    return `<${fieldName || "texto"}>`;
  }
  if (name === "ZodNumber") return 0;
  if (name === "ZodBoolean") return false;
  if (name === "ZodNull") return null;
  if (name === "ZodLiteral") return schema._def.value;
  if (name === "ZodEnum") return schema._def.values[0];
  if (name === "ZodArray") {
    const child = exampleFor(schema._def.type, fieldName, depth + 1);
    return child === undefined ? [] : [child];
  }
  if (name === "ZodObject") {
    const result = {};
    for (const [key, value] of Object.entries(schema._def.shape())) {
      const child = exampleFor(value, key, depth + 1);
      if (child !== undefined) result[key] = child;
    }
    return result;
  }
  if (name === "ZodUnion") return exampleFor(schema._def.options[0], fieldName, depth + 1);
  if (name === "ZodRecord") return {};
  return null;
}

function endpointUrl(endpoint) {
  switch (endpoint.type) {
    case "pd":
      return `https://pd.{shard}.a.pvp.net/${endpoint.suffix}`;
    case "shared":
      return `https://shared.{shard}.a.pvp.net/${endpoint.suffix}`;
    case "glz":
      return `https://glz-{region}-1.{shard}.a.pvp.net/${endpoint.suffix}`;
    case "local":
      return `https://127.0.0.1:{port}/${endpoint.suffix}`;
    default:
      return endpoint.suffix;
  }
}

function categoryName(category) {
  if (Array.isArray(category)) return category.join(" / ");
  return category || "Other";
}

function normalizeVariableName(name) {
  return name.trim().replace(/^\{|\}$/g, "").trim();
}

function variableEntries(endpoint, urlTemplate) {
  const explicit = new Map();
  for (const [name, schema] of endpoint.variables ?? []) {
    explicit.set(normalizeVariableName(name).toLowerCase(), {
      name: normalizeVariableName(name),
      ...schemaInfo(schema),
    });
  }

  const seen = new Set();
  const result = [];
  for (const match of urlTemplate.matchAll(/\{([^{}]+)\}/g)) {
    const name = normalizeVariableName(match[1]);
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(explicit.get(key) ?? {
      name,
      type: "string",
      optional: false,
      nullable: false,
      description: "",
    });
  }
  return result;
}

const serialized = Object.entries(endpoints).map(([id, endpoint]) => {
  const urlTemplate = endpointUrl(endpoint);
  const method = endpoint.method ?? "GET";
  const bodyExample = endpoint.body ? exampleFor(endpoint.body) : undefined;
  return {
    id,
    name: endpoint.name,
    query_name: endpoint.queryName ?? "",
    description: endpoint.description,
    category: categoryName(endpoint.category),
    transport: "http",
    endpoint_type: endpoint.type,
    method,
    url_template: urlTemplate,
    docs_url: `https://valapidocs.techchrism.me/endpoint/${endpoint.name.toLowerCase().replaceAll(" ", "-")}`,
    requirements: {
      token: Boolean(endpoint.riotRequirements?.token),
      entitlement: Boolean(endpoint.riotRequirements?.entitlement),
      client_version: Boolean(endpoint.riotRequirements?.clientVersion),
      client_platform: Boolean(endpoint.riotRequirements?.clientPlatform),
      local_auth: Boolean(endpoint.riotRequirements?.localAuth),
    },
    headers: Object.fromEntries(endpoint.headers ?? []),
    variables: variableEntries(endpoint, urlTemplate),
    query: [...(endpoint.query ?? [])].map(([name, schema]) => ({
      name,
      ...schemaInfo(schema),
    })),
    body_schema: endpoint.body ? schemaInfo(endpoint.body) : null,
    body_example: bodyExample === undefined ? "" : JSON.stringify(bodyExample, null, 2),
    mutating: ["POST", "PUT", "PATCH", "DELETE"].includes(method),
  };
});

serialized.push(
  {
    id: "localWebSocketEndpoint",
    name: "Local WebSocket",
    query_name: "",
    description: "Connect to the Riot local websocket and subscribe to live JSON API events.",
    category: "Local Endpoints",
    transport: "websocket",
    endpoint_type: "other",
    method: "WSS",
    url_template: "wss://127.0.0.1:{port}",
    docs_url: "https://valapidocs.techchrism.me/endpoint/local-web-socket",
    requirements: {
      token: false,
      entitlement: false,
      client_version: false,
      client_platform: false,
      local_auth: true,
    },
    headers: {},
    variables: [{ name: "port", type: "number", optional: false, nullable: false, description: "" }],
    query: [],
    body_schema: null,
    body_example: "[5, \"OnJsonApiEvent\"]",
    mutating: false,
  },
  {
    id: "xmppEndpoint",
    name: "XMPP Connection",
    query_name: "",
    description: "Open an authenticated TLS XMPP connection to Riot chat and exchange raw XML messages.",
    category: "XMPP",
    transport: "xmpp",
    endpoint_type: "other",
    method: "TCP",
    url_template: "xmpps://auto",
    docs_url: "https://valapidocs.techchrism.me/endpoint/xmpp-connection",
    requirements: {
      token: true,
      entitlement: true,
      client_version: false,
      client_platform: false,
      local_auth: false,
    },
    headers: {},
    variables: [],
    query: [],
    body_schema: null,
    body_example: "",
    mutating: false,
  },
);

serialized.sort((a, b) =>
  a.category.localeCompare(b.category) || a.name.localeCompare(b.name) || a.method.localeCompare(b.method),
);

const payload = {
  metadata: {
    source: "https://github.com/techchrism/valorant-api-docs",
    package: "valorant-api-types",
    package_version: packageJson.version,
    generated_at: new Date().toISOString(),
    endpoint_count: serialized.length,
  },
  endpoints: serialized,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Exported ${serialized.length} endpoints to ${outputPath}`);
