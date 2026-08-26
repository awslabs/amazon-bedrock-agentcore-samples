import { CfnOutput, Stack } from 'aws-cdk-lib';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import { Construct } from 'constructs';

/**
 * The WAF web ACL in front of the distribution — one ACL covering the SPA *and* the API.
 *
 * **One ACL, and it covers the distribution rather than every route to the API.** The distribution
 * serves the bundle and forwards `/v1/*` to the conversation API (necessary for the
 * `SameSite=Strict` session cookie — see `frontend-hosting.ts`), so one `CLOUDFRONT`-scoped ACL sits
 * in front of both as they are reached *through CloudFront*.
 *
 * **This comment used to claim the API stage "no longer receives public traffic directly", and that
 * was false.** The conversation API's `execute-api` hostname is public and is published to Parameter
 * Store (`/multi-tenant-travel/conversation-api/url`) for the SPA build and the verification scripts
 * to read. A caller who addresses it directly bypasses this ACL entirely — the managed rule sets and
 * the edge rate limit included. The reasoning was backwards: the same-origin design made CloudFront
 * the *normal* path, not the only one.
 *
 * **Left open deliberately, with the reasons stated so the next reader can weigh them.** The direct
 * path still requires a valid session cookie and refuses cross-origin POSTs, so this is a
 * defence-in-depth gap rather than an open door. **API Gateway stage throttling — 20 req/s, burst 40,
 * configured in `conversation-api.ts` — is on the stage itself**, so it applies to direct callers too,
 * and it is the control that bounds model spend, which is the axis that actually costs money here.
 * Closing the gap properly means a second, *regional* ACL at roughly another $10/month, on a feature
 * that is opt-in precisely so a reader is not surprised by a standing charge.
 *
 * For a deployment carrying real traffic, add it: a `REGIONAL`-scoped ACL associated with the
 * conversation API's stage ARN, mirroring the rules below. That is the change, and this is where it
 * goes.
 *
 * **`CLOUDFRONT` scope means this ACL must live in `us-east-1`** — a genuine constraint rather than a
 * preference, and the reason there is no second region to think about here: the whole stack is
 * `us-east-1` already. A deployer who moves the stack elsewhere keeps this one resource behind, which
 * is why the scope is stated in the construct rather than assumed.
 *
 * **What this defends and what it does not.** It is a volumetric and known-bad-signature layer: rate
 * limiting, and AWS's managed rule sets. It is emphatically *not* the tenancy boundary — that is
 * Cognito's verified claims, the gateway interceptor, Cedar, and `dynamodb:LeadingKeys`. Nothing here
 * knows what a tenant is. Worth stating plainly because a WAF in an architecture diagram invites the
 * assumption that it is doing authorisation work.
 */
export class EdgeProtection extends Construct {
  public readonly webAcl: wafv2.CfnWebACL;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const stack = Stack.of(this);

    this.webAcl = new wafv2.CfnWebACL(this, 'WebAcl', {
      name: `${stack.stackName}-edge`,
      // **`CLOUDFRONT`, which forces `us-east-1`.** A `REGIONAL` ACL cannot attach to a
      // distribution, and the failure is at deploy time with a message about the scope rather than
      // about the association.
      scope: 'CLOUDFRONT',
      // Default allow, with rules that block. The inverse (default block, rules that allow) is the
      // right shape for an internal tool with a known caller set, and the wrong one here: this is a
      // public site whose legitimate traffic is "anyone with the link".
      defaultAction: { allow: {} },
      description: 'Rate limiting and AWS managed rules for the SPA and conversation API',
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: `${stack.stackName}-edge`,
        sampledRequestsEnabled: true,
      },
      rules: [
        /**
         * **Rate limiting first, and deliberately the tightest rule in the list.**
         *
         * This is the one rule that defends something specific to *this* application: every request
         * to `/v1/conversation/*` can start an agent turn, and an agent turn spends model tokens.
         * So the abuse case is not data theft, it is **someone running up a bill** — which no managed
         * rule set knows to look for, because there is nothing malicious about the request itself.
         *
         * 300 per 5 minutes per IP, scoped to the API path. A real conversation is a handful of
         * requests per turn, so a person cannot reach this by using the product; a script can reach
         * it immediately. Scoped to the path rather than the whole site because the SPA's own asset
         * fetches are legitimately bursty and share the IP.
         */
        {
          name: 'ConversationRateLimit',
          priority: 0,
          action: { block: {} },
          statement: {
            rateBasedStatement: {
              limit: 300,
              // Per IP. `FORWARDED_IP` would be the choice behind a further proxy; there is none
              // here, and trusting a client-supplied header for rate limiting would let a caller
              // rotate their own bucket.
              aggregateKeyType: 'IP',
              scopeDownStatement: {
                byteMatchStatement: {
                  fieldToMatch: { uriPath: {} },
                  positionalConstraint: 'STARTS_WITH',
                  searchString: '/v1/conversation',
                  textTransformations: [{ priority: 0, type: 'NONE' }],
                },
              },
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'ConversationRateLimit',
            sampledRequestsEnabled: true,
          },
        },

        /**
         * A second, looser limit across everything else, so the site as a whole has a ceiling.
         *
         * Higher than the API limit because one page load is many requests. This exists to bound a
         * crawler or a stuck client, not to catch abuse — the rule above does that.
         */
        {
          name: 'SiteRateLimit',
          priority: 1,
          action: { block: {} },
          statement: {
            rateBasedStatement: { limit: 2000, aggregateKeyType: 'IP' },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'SiteRateLimit',
            sampledRequestsEnabled: true,
          },
        },

        /**
         * AWS's baseline managed rules.
         *
         * **Two rules are neutralised to `Count`, and the choice of `Count` over `Allow` is the
         * whole point.** `SizeRestrictions_BODY` rejects bodies over 8 KB and a conversation turn
         * legitimately carries a long prompt, so leaving it enforcing would block real messages with
         * a 403 that looks like a broken API. `NoUserAgent_HEADER` blocks requests with no
         * user agent, which is what `urllib` sends — including our own verification scripts, and a
         * control that blocks the test suite gets switched off rather than fixed.
         *
         * **These were `allow`, which was a full web-ACL bypass.** Per AWS: *Allow and Block are
         * terminating actions, which stop all other processing of the web ACL. Count is
         * non-terminating.* So an `allow` override did not "exclude" the rule — it short-circuited
         * the entire ACL for anything that matched it. Any request omitting a `User-Agent` header,
         * or padded past 8 KB, was allowed outright and never reached `KnownBadInputs` or the IP
         * reputation list below. One missing header defeated everything.
         *
         * `Count` neutralises the rule without terminating: WAF records the match as a metric and
         * carries on through the remaining rule groups, which is what "exclude this one rule, keep
         * the other twenty-odd" actually requires.
         */
        {
          name: 'AWSManagedRulesCommonRuleSet',
          priority: 2,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesCommonRuleSet',
              ruleActionOverrides: [
                { name: 'SizeRestrictions_BODY', actionToUse: { count: {} } },
                { name: 'NoUserAgent_HEADER', actionToUse: { count: {} } },
              ],
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'CommonRuleSet',
            sampledRequestsEnabled: true,
          },
        },

        /**
         * Known-bad inputs: path traversal, common exploit strings, host-header injection.
         *
         * Cheap and uncontroversial — nothing this application legitimately does resembles the
         * signatures here.
         */
        {
          name: 'AWSManagedRulesKnownBadInputsRuleSet',
          priority: 3,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesKnownBadInputsRuleSet',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'KnownBadInputs',
            sampledRequestsEnabled: true,
          },
        },

        /**
         * IP reputation — known scanners, botnets, and sources of automated abuse.
         *
         * Last in priority because it is the broadest and the most likely to have an opinion about a
         * legitimate caller behind a shared address. Kept because a public demo link is exactly what
         * automated scanners find.
         */
        {
          name: 'AWSManagedRulesAmazonIpReputationList',
          priority: 4,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesAmazonIpReputationList',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'IpReputation',
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    new CfnOutput(this, 'WebAclArn', {
      value: this.webAcl.attrArn,
      description: 'WAF web ACL attached to the CloudFront distribution',
    });
  }
}
