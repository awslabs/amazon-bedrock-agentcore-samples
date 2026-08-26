import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

/**
 * Identity for the assistant: who is asking, and on whose behalf.
 *
 * Cognito is a real OIDC provider with a discovery endpoint, which is the whole
 * reason no custom verifier Lambda appears anywhere in this sample. AgentCore
 * Runtime validates the inbound token natively against the discovery URL; a
 * verifier hop is what you build for a token that *lacks* one, and teaching it as
 * the default would be misleading.
 *
 * **The token carries identity, not authorization.** Three custom claims, all
 * facts a corporate directory genuinely holds about a person. Notably absent is
 * `can_book_for`: an arranger relationship lives in the travel platform, not the
 * IdP, so it is resolved live (see `backend/app/service/arrangers.py`). Copying it
 * into a token would duplicate an authorization fact out of the system that owns
 * it, leave it stale for the token's whole lifetime, and fail outright where the
 * relationship is a rule ("arranger for cost centre 4400") rather than a list.
 *
 * **In production** a corporate customer federates their own IdP (Okta, Entra) and
 * these three claims arrive by SAML/OIDC attribute mapping from their directory —
 * which works precisely because they are identity facts. That path is documented
 * rather than built, because direct Cognito users keep the sample runnable by
 * anyone with an AWS account and no IdP to configure.
 */

/** Custom attributes, unprefixed. Cognito exposes them as `custom:<name>`. */
const TENANT_ATTR = 'tenant_id';
const TRAVELER_ATTR = 'traveler_id';
const ROLE_ATTR = 'role';

/**
 * The OAuth scopes, named after what they let a caller *do*.
 *
 * Two, deliberately — never one per tool. Per-tool scopes would mean an IdP
 * change for every new tool, and they duplicate Cedar's job at a layer that
 * cannot see runtime context. Scopes are the coarse outer gate ("may this caller
 * reach this class of tool"); Cedar answers the specific question ("may Adaeze
 * book for Priya"), because that depends on facts only known at request time.
 */
/**
 * Identifier of the resource server the scopes hang off.
 *
 * Cognito composes a scope as `<resource-server-id>/<scope-name>` — the separator
 * is a slash, not a colon, so these read `travel/read` rather than the
 * `travel:read` an OAuth-conventions habit would produce. Worth stating because
 * the Gateway's `--allowed-scopes` must match the *emitted* string exactly, and a
 * colon there fails closed with no useful error.
 */
const RESOURCE_SERVER_ID = 'travel';

export const SCOPE_READ = `${RESOURCE_SERVER_ID}/read`;
export const SCOPE_BOOK = `${RESOURCE_SERVER_ID}/book`;

/**
 * **Users are not defined here.** They are created by
 * `backend/seed/users.py`, which derives them from the traveller fixtures rather
 * than restating them.
 *
 * Two reasons. CDK cannot set a password, so a user would need a script
 * regardless. More importantly, a traveller's opaque id (`trv_31d81fa59772`) must
 * be identical in the token and in the profile store — and duplicating it into
 * TypeScript would create a second source of truth for an id whose whole purpose
 * is to join two systems. A mismatch there authenticates successfully and then
 * resolves to no profile, which reads like a broken backend rather than a stale
 * fixture.
 */
export class Identity extends Construct {
  public readonly userPool: cognito.UserPool;
  /** Used by the browser/CLI demo: authorization-code flow, no client secret. */
  public readonly appClient: cognito.UserPoolClient;
  /** Used by tests and the terminal demo: username/password, no hosted UI hop. */
  public readonly cliClient: cognito.UserPoolClient;
  public readonly domain: cognito.UserPoolDomain;
  /** OIDC discovery URL — what Runtime and Gateway validate tokens against. */
  public readonly discoveryUrl: string;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const stack = Stack.of(this);
    const stackName = stack.stackName;

    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `${stackName}-travelers`,
      selfSignUpEnabled: false, // travellers are onboarded by their employer
      signInAliases: { username: true, email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
        fullname: { required: false, mutable: true },
      },
      customAttributes: {
        // **Immutable once set.** A traveller must not be able to edit their own
        // tenant, and mutability here is not a policy knob — Cognito fixes it at
        // creation, so getting it wrong means replacing the pool later.
        [TENANT_ATTR]: new cognito.StringAttribute({ minLen: 2, maxLen: 32, mutable: false }),
        [TRAVELER_ATTR]: new cognito.StringAttribute({ minLen: 8, maxLen: 32, mutable: false }),
        // Role is mutable: someone can genuinely become an arranger. It is still
        // identity rather than authorization — it says what kind of user they are,
        // not what they may do to whom.
        [ROLE_ATTR]: new cognito.StringAttribute({ minLen: 4, maxLen: 16, mutable: true }),
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      // A sample must leave nothing behind. Production would RETAIN — deleting a
      // user pool is unrecoverable and takes every user identity with it.
      removalPolicy: RemovalPolicy.DESTROY,
    });

    /**
     * Mirror identity claims onto the **access token**, and add the entitled
     * scopes.
     *
     * Necessary because Cognito puts custom attributes in the ID token only,
     * while the bearer that reaches Runtime and the Gateway is an access token —
     * so without this the interceptor has no `tenant_id` to inject. Cognito also
     * only issues custom scopes through the OAuth endpoints, so a token from the
     * password flow (the terminal demo, the integration tests) would otherwise
     * carry none.
     *
     * **Not the trigger this design rejected.** That one computed `can_book_for`,
     * an authorization fact owned by the travel platform. This one copies identity
     * facts the user pool already holds. See `lambda/pre-token/index.mjs`.
     */
    const preTokenFn = new lambda.Function(this, 'PreTokenGeneration', {
      functionName: `${stackName}-pre-token`,
      // Node rather than Python: this runs on the sign-in path, so cold start is
      // user-visible latency, and the function is 40 lines with no dependencies.
      runtime: lambda.Runtime.NODEJS_24_X,
      architecture: lambda.Architecture.ARM_64,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(REPO_ROOT, 'infra/lambda/pre-token')),
      timeout: Duration.seconds(5),
      memorySize: 256,
      // Sign-in traffic is the highest-volume path here and these logs are
      // diagnostic, not audit — CloudTrail is the authoritative record.
      logGroup: new logs.LogGroup(this, 'PreTokenLogGroup', {
        logGroupName: `/aws/lambda/${stackName}-pre-token`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: RemovalPolicy.DESTROY,
      }),
    });

    // V2_0 is what makes access-token customization possible at all; V1_0 can only
    // touch the ID token, which is the problem this trigger exists to solve.
    // Requires the Essentials feature plan (the default for a new pool).
    this.userPool.addTrigger(
      cognito.UserPoolOperation.PRE_TOKEN_GENERATION_CONFIG,
      preTokenFn,
      cognito.LambdaVersion.V2_0,
    );

    // Scopes must exist on a resource server before any client can request them.
    const resourceServer = this.userPool.addResourceServer('TravelResourceServer', {
      identifier: RESOURCE_SERVER_ID,
      userPoolResourceServerName: 'Travel tools',
      scopes: [
        new cognito.ResourceServerScope({
          scopeName: 'read',
          scopeDescription: 'Search, trips, profile, policy, hotel details',
        }),
        new cognito.ResourceServerScope({
          scopeName: 'book',
          scopeDescription: 'Hold, confirm, modify and cancel reservations',
        }),
      ],
    });

    // A hosted-UI domain is required for the authorization-code flow, and it is
    // also the cheapest way for a reader to obtain a real token without writing
    // an auth client. Prefixed with the account id because the prefix is global.
    this.domain = this.userPool.addDomain('HostedUi', {
      cognitoDomain: { domainPrefix: `multi-tenant-travel-${stack.account}` },
    });

    const readScope = cognito.OAuthScope.resourceServer(resourceServer, {
      scopeName: 'read',
      scopeDescription: 'Search, trips, profile, policy, hotel details',
    });
    const bookScope = cognito.OAuthScope.resourceServer(resourceServer, {
      scopeName: 'book',
      scopeDescription: 'Hold, confirm, modify and cancel reservations',
    });

    this.appClient = this.userPool.addClient('WebClient', {
      userPoolClientName: `${stackName}-web`,
      // No secret: a browser cannot keep one, and pretending otherwise is a
      // common way samples teach an insecure pattern.
      generateSecret: false,
      authFlows: { userSrp: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, readScope, bookScope],
        // The local SPA's dev server. The **deployed** callback is added by
        // `addCallbackUrl`, because it redirects to the conversation API rather than to the
        // frontend — the authorization code is exchanged server-side so the tokens never
        // reach the browser, and a callback pointing at the SPA would undo that.
        callbackUrls: ['http://localhost:5173/callback'],
        logoutUrls: ['http://localhost:5173'],
      },
      // Short access tokens because the assistant does not rely on token lifetime
      // for session continuity — the interceptor mints per-request context, so a
      // conversation outliving an access token is not a problem to design around.
      accessTokenValidity: Duration.minutes(60),
      idTokenValidity: Duration.minutes(60),
      refreshTokenValidity: Duration.days(30),
      preventUserExistenceErrors: true,
    });

    // A separate client for the terminal demo and integration tests: the SRP
    // password flow yields a token in one call, with no browser redirect. Kept
    // distinct from the web client so the demo path and the production-shaped path
    // are visibly different things rather than one client with both enabled.
    this.cliClient = this.userPool.addClient('CliClient', {
      userPoolClientName: `${stackName}-cli`,
      generateSecret: false,
      authFlows: { userSrp: true, userPassword: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, readScope, bookScope],
        callbackUrls: ['http://localhost:5173/callback'],
      },
      accessTokenValidity: Duration.minutes(60),
      idTokenValidity: Duration.minutes(60),
      preventUserExistenceErrors: true,
    });

    this.discoveryUrl =
      `https://cognito-idp.${stack.region}.amazonaws.com/` +
      `${this.userPool.userPoolId}/.well-known/openid-configuration`;

    // **SSM rather than CloudFormation exports.** The AgentCore CLI drives a
    // separate CDK app, so these values cross an app boundary; an export would
    // also lock — CloudFormation refuses to delete an export while a consumer
    // imports it, which deadlocks any deploy that changes the wiring. Parameters
    // are read at deploy time and never lock.
    const parameters: Record<string, string> = {
      'user-pool-id': this.userPool.userPoolId,
      'user-pool-arn': this.userPool.userPoolArn,
      'web-client-id': this.appClient.userPoolClientId,
      'cli-client-id': this.cliClient.userPoolClientId,
      'discovery-url': this.discoveryUrl,
      'hosted-ui-domain': this.domain.baseUrl(),
      'scope-read': SCOPE_READ,
      'scope-book': SCOPE_BOOK,
    };

    for (const [name, value] of Object.entries(parameters)) {
      new ssm.StringParameter(
        this,
        `Param${name.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase())}`,
        {
          parameterName: `/multi-tenant-travel/identity/${name}`,
          stringValue: value,
          description: `Identity: ${name}`,
        },
      );
    }

    new CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new CfnOutput(this, 'CliClientId', {
      value: this.cliClient.userPoolClientId,
      description: 'Client for the terminal demo (username/password flow)',
    });
    new CfnOutput(this, 'DiscoveryUrl', {
      value: this.discoveryUrl,
      description: 'What Runtime and Gateway validate inbound tokens against',
    });
  }

  /**
   * Register another OAuth callback URL on the web client.
   *
   * Needed because the deployed callback belongs to the *conversation API*, which is constructed
   * after this one — so its URL is not knowable here. Cognito rejects a redirect it has not been
   * told about, and the failure lands in the hosted UI with a message that says nothing about
   * which URL was expected.
   *
   * Reaches through to the L1 rather than taking the URL as a prop: an `Identity` that had to be
   * told about the conversation API would invert the dependency, and identity legitimately knows
   * nothing about who consumes it.
   */
  public addCallbackUrl(url: string): void {
    const client = this.appClient.node.defaultChild as cognito.CfnUserPoolClient;
    // `CallbackURLs` — capitalised as CloudFormation spells it, not as CDK's L2 does. A camelCase
    // key here is silently ignored, leaving a client that looks configured and rejects the
    // redirect.
    const existing = (client.callbackUrLs ?? []) as string[];
    client.callbackUrLs = [...new Set([...existing, url])];
  }

  /**
   * Register a sign-out destination on the web client.
   *
   * Separate from `addCallbackUrl` because they are different URLs: the callback belongs to the
   * conversation API (the code is exchanged server-side) while sign-out returns to the *site*. Using
   * one for both would either send the traveller to a JSON endpoint or hand the code to the browser.
   */
  public addLogoutUrl(url: string): void {
    const client = this.appClient.node.defaultChild as cognito.CfnUserPoolClient;
    const existing = (client.logoutUrLs ?? []) as string[];
    client.logoutUrLs = [...new Set([...existing, url])];
  }
}
