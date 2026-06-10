# AgentCore Cedar Policy Syntax Requirements

## Critical Constraint: Resource Must Be Typed

AgentCore's CreatePolicy API rejects policies with wildcard `resource` scope.
Every Cedar statement **must** constrain the resource to `AgentCore::Gateway`:

```cedar
// GOOD — resource constrained to Gateway type
permit(principal, action, resource is AgentCore::Gateway);

// BAD — wildcard resource rejected with:
// "a wildcard resource was detected. Please constrain the resource
//  to a specific AgentCore::Gateway resource or to the AgentCore::Gateway resource type."
permit(principal, action, resource);
```

## Correct Patterns

```cedar
// Permit all tool calls (for LOG_ONLY observability)
permit(principal, action, resource is AgentCore::Gateway);

// Forbid a specific tool based on context
forbid(principal, action, resource is AgentCore::Gateway)
  when { context has "toolName" && context.toolName == "dangerous-tool" };

// Conditional forbid (deny unless condition met)
forbid(principal, action, resource is AgentCore::Gateway)
  when { context has "toolName" && context.toolName == "create-change-request" && !(context has "reason") };
```

## Invalid Patterns (will fail at deploy)

```cedar
// BAD — Resource:: namespace doesn't exist in AgentCore
forbid(principal, action == Action::"InvokeTool", resource == Resource::"create-change-request");

// BAD — wildcard resource (even with typed action)
permit(principal, action, resource);

// BAD — unquoted string values
when { context.toolName == create-change-request };
```

## Context Fields Available

During gateway tool invocation, the Cedar `context` object contains:
- `context.toolName` — name of the tool being invoked
- Additional fields depend on the gateway configuration

## Validation Mode

| Mode | Effect |
|------|--------|
| `IGNORE_ALL_FINDINGS` | Policy is deployed without Cedar schema validation (recommended for LOG_ONLY) |
| `FAIL_ON_ANY_FINDINGS` | Policy must pass Cedar schema validation against the gateway's schema |

Use `IGNORE_ALL_FINDINGS` when context field names are not registered in the gateway's Cedar schema.

## References

- Error: "Invalid resource ARN provided in policy's resource scope" → Use typed resource name, not ARN string
- Error: "wildcard resource was detected" → Add `resource is AgentCore::Gateway`
