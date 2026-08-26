import { CfnOutput, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

/**
 * The private network the capability and data layers live in.
 *
 * **The first thing in this sample with a standing hourly cost, which is why it was priced before it
 * was built.** Everything else here is pay-per-request: an untouched deployment costs approximately
 * nothing. An interface endpoint bills `$0.01/hour` **per Availability Zone** whether or not a single
 * request crosses it — so eleven services across two AZs is ~$161/month idle, more than the rest of
 * this sample combined at sample volumes. The Cost section of `README.md` has the full comparison
 * against the alternatives.
 *
 * **No NAT gateway, deliberately.** A NAT is cheaper ($36.50/month against ~$161) and it would
 * falsify the claim this whole layer exists to support: traffic to Bedrock, DynamoDB and the backend
 * would leave through a public IP and traverse the internet. It also inverts at volume — $0.045/GB
 * against $0.01/GB. Having no NAT at all is additionally the strongest available guard against the
 * classic surprise bill, where a NAT quietly carries model responses at 4.5× the endpoint rate.
 *
 * **Two AZs, not one.** Halving to one AZ would save ~$65/month and let a single AZ impairment take
 * the entire capability layer offline. That is a reasonable knob to turn in your own dev account —
 * `maxAzs: 1` below — but it is not the default here, because a sample that demonstrates isolation
 * should not ship a single point of failure to save a reader money they have already opted into
 * spending with `--private`.
 *
 * **What is deliberately *not* in this VPC:** the conversation API and the gateway interceptor. See
 * `SUBNET_NAME` below and the note on `cognito` in `INTERFACE_ENDPOINTS`.
 */
export class Network extends Construct {
  public readonly vpc: ec2.Vpc;

  /**
   * The security group every in-VPC component shares.
   *
   * **One group rather than one per component, because the isolation that matters here is not
   * between our own Lambdas.** They all reach the same endpoints and none of them accepts inbound
   * connections from another — a tool Lambda talks to the backend through API Gateway, never
   * directly. Per-component groups would be five near-identical rules maintained separately, and
   * the reader would be left looking for a distinction that does not exist.
   *
   * Where isolation *is* enforced: the endpoint policies below, the Gateway's Cedar policies, the
   * interceptor's tenant injection, and `TenantIsolation`'s per-request role. A security group
   * cannot express any of those, so pretending it contributes would be misleading.
   */
  public readonly securityGroup: ec2.SecurityGroup;

  /** Interface endpoints by service key, so an endpoint policy can be attached per service. */
  public readonly endpoints: Record<string, ec2.InterfaceVpcEndpoint> = {};

  /**
   * Subnets to attach in-VPC compute to — private, with no route to the internet at all.
   *
   * `PRIVATE_ISOLATED` rather than `PRIVATE_WITH_EGRESS`: the latter implies a NAT, and CDK would
   * create one. Isolated subnets make the no-internet property structural rather than a convention
   * someone could undo by adding a route.
   */
  public get subnets(): ec2.SubnetSelection {
    return { subnetType: ec2.SubnetType.PRIVATE_ISOLATED };
  }

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const stackName = Stack.of(this).stackName;

    this.vpc = new ec2.Vpc(this, 'Vpc', {
      vpcName: `${stackName}-vpc`,
      // A /20 is far more address space than this sample needs, and picking it anyway is the point:
      // Lambda consumes ENIs from these subnets, and running out of addresses surfaces as
      // `EC2ThrottledException` on invoke — an error whose text says nothing about IP exhaustion.
      // Room is the cheapest possible insurance against a confusing failure.
      ipAddresses: ec2.IpAddresses.cidr('10.30.0.0/20'),
      maxAzs: 2,
      // **Zero NAT gateways stated explicitly.** CDK's default is one per AZ, so leaving this out
      // would silently add $73/month and a public egress path — the exact thing the topology rejects.
      natGateways: 0,
      subnetConfiguration: [
        {
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
      // Required for interface endpoints' private DNS to resolve. On by default; named because
      // turning it off breaks every endpoint below in a way that looks like a networking fault
      // rather than a VPC setting.
      enableDnsSupport: true,
      enableDnsHostnames: true,
      /**
       * Flow logs — **the observability counterpart to the endpoint policies.**
       *
       * Worth the ingestion cost specifically because this VPC has *no internet route*: the
       * interesting question here is not "who talked to the outside world" but "what tried to and
       * failed", and a `REJECT` record is how a missing endpoint stops being a mystery timeout. That
       * is precisely the failure mode this migration produced twice (`sts:TagSession`,
       * `ApplyGuardrail`), diagnosed both times from application logs rather than from the network.
       *
       * Two weeks' retention: a flow log is diagnostic, and CloudTrail remains the audit record.
       */
      flowLogs: {
        rejects: {
          trafficType: ec2.FlowLogTrafficType.ALL,
          destination: ec2.FlowLogDestination.toCloudWatchLogs(
            new logs.LogGroup(this, 'FlowLogs', {
              logGroupName: `/aws/vpc/${stackName}-flow-logs`,
              retention: logs.RetentionDays.TWO_WEEKS,
              removalPolicy: RemovalPolicy.DESTROY,
            }),
          ),
        },
      },
    });

    this.securityGroup = new ec2.SecurityGroup(this, 'ComputeSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${stackName}-compute`,
      description: 'In-VPC compute: tool Lambdas, backend, agent runtime',
      // Outbound to the endpoints. Unrestricted *within the VPC* is the honest description — there
      // is no internet route for it to reach, so the constraint is topological rather than a rule.
      allowAllOutbound: true,
    });

    /**
     * The endpoints' own security group, separate from the compute one.
     *
     * **Not the same group with a self-referencing rule**, which is the tempting shortcut. Two
     * groups make the direction of trust readable: compute initiates, endpoints accept. It also
     * means adding a second compute group later (a VPC Lambda that should reach only *some*
     * endpoints, say) is a rule change rather than a restructure.
     */
    const endpointSecurityGroup = new ec2.SecurityGroup(this, 'EndpointSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${stackName}-endpoints`,
      // **ASCII only.** EC2 rejects a security group description containing anything else, with
      // `Character sets beyond ASCII are not supported` — so the em dash used everywhere else in this
      // repo's prose fails here, at deploy time rather than at synth. The `CfnOutput` descriptions
      // below are CloudFormation's own and have no such restriction, which is why they keep theirs.
      description: 'Interface VPC endpoints: accepts HTTPS from in-VPC compute only',
      allowAllOutbound: false,
    });
    endpointSecurityGroup.addIngressRule(
      this.securityGroup,
      ec2.Port.tcp(443),
      'HTTPS from in-VPC compute',
    );

    /**
     * **Gateway endpoints first, because they are free and they carry the highest-volume traffic.**
     *
     * S3 and DynamoDB are the only two services offering a gateway endpoint: a route-table entry
     * rather than an ENI, so there is no hourly charge and no per-GB charge. Every byte the backend
     * reads from DynamoDB and every policy document it fetches from S3 crosses these for nothing.
     *
     * Worth internalising as a rule of thumb: if a service offers a gateway endpoint, there is
     * never a reason to pay for an interface one.
     */
    this.vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
      subnets: [this.subnets],
    });
    this.vpc.addGatewayEndpoint('DynamoDbEndpoint', {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
      subnets: [this.subnets],
    });

    for (const [key, spec] of Object.entries(INTERFACE_ENDPOINTS)) {
      this.endpoints[key] = this.vpc.addInterfaceEndpoint(spec.id, {
        service: new ec2.InterfaceVpcEndpointService(
          `com.amazonaws.${Stack.of(this).region}.${spec.serviceName}`,
          443,
        ),
        subnets: this.subnets,
        securityGroups: [endpointSecurityGroup],
        // What makes the endpoint transparent: the SDK keeps calling
        // `bedrock-runtime.us-east-1.amazonaws.com` and the VPC resolver answers with the ENI's
        // private address. Without it every caller would need an `endpoint_url` override, which
        // would put infrastructure detail into application code.
        privateDnsEnabled: true,
      });
    }

    new CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC holding the capability and data layers',
    });
    new CfnOutput(this, 'PrivateSubnetIds', {
      value: this.vpc.selectSubnets(this.subnets).subnetIds.join(','),
      description: 'Private isolated subnets — for agentcore.json networkConfig.subnets',
    });
    new CfnOutput(this, 'ComputeSecurityGroupId', {
      value: this.securityGroup.securityGroupId,
      description:
        'Shared compute security group — for agentcore.json networkConfig.securityGroups',
    });
  }

  /**
   * Restrict an endpoint to specific actions and resources.
   *
   * **Because the default is `*` on `*`.** An interface endpoint with no policy is a private route
   * to the entire service, which throws away most of the reason to have paid for it: the useful
   * property is not "this traffic stays off the internet" but "this VPC can reach *only these
   * things*". Two independent controls then have to fail before a compromised Lambda reaches an
   * unrelated table — its execution role, and this.
   *
   * Left deliberately per-service rather than applied in a loop with one shared policy, because the
   * correct policy is different for each and a generic one would be theatre.
   */
  public restrictEndpoint(key: string, statements: iam.PolicyStatement[]): void {
    const endpoint = this.endpoints[key];
    if (!endpoint) {
      // A typo'd key would otherwise silently leave an endpoint wide open — the failure mode this
      // method exists to prevent. Loud at synth, before anything is deployed.
      throw new Error(`no interface endpoint registered under '${key}'`);
    }
    for (const statement of statements) {
      endpoint.addToPolicy(statement);
    }
  }
}

/**
 * The interface endpoints, one per service anything in the VPC actually calls.
 *
 * **Enumerated from `boto3.client(...)` call sites rather than from a checklist**, because the cost
 * is per service and a speculative endpoint is $14.60/month for nothing. Each entry names its caller
 * so a future reader can delete it when that caller goes away.
 *
 * Two services are notable by their absence:
 *
 * **`cognito-idp`** — the interceptor fetches Cognito's JWKS, which *is* served from
 * `cognito-idp.us-east-1.amazonaws.com` and would be covered. But the interceptor stays outside the
 * VPC (see below), so nothing in the VPC needs it.
 *
 * **The Cognito hosted UI** — `<domain>.auth.<region>.amazoncognito.com`, where the BFF's
 * `/oauth2/authorize`, `/oauth2/token` and `/oauth2/userInfo` calls go. **There is no VPC endpoint
 * for it at all**, verified by scanning every endpoint service's private DNS names for
 * `amazoncognito`: no match. `cognito-idp` is the control plane and serves none of those paths.
 *
 * That single fact is what puts the **conversation API outside the VPC**, and it is a better
 * decision than the NAT it would otherwise need. The BFF is already public by necessity — it is a
 * CloudFront origin serving a browser — so putting it in a VPC to then punch an egress hole for a
 * public identity provider would buy an ENI cold start on the user-facing path and a NAT bill, in
 * exchange for nothing. The interceptor follows it out for the same reason: it too talks only to
 * Cognito.
 *
 * The resulting seam states cleanly: **the capability layer and the data layer are private; the
 * front door is public, because a front door is.**
 *
 * **A CloudWatch Logs endpoint is *not* needed for Lambda's own logging**, which is the reflex to
 * resist: the execution environment ships those, and that path does not traverse the function's VPC
 * ENI. Every function keeps logging normally without one. The `logs` entry below exists for a
 * different reason — VPC flow logs — and carries its own justification.
 */
const INTERFACE_ENDPOINTS: Record<string, { id: string; serviceName: string; usedBy: string }> = {
  /**
   * Amazon Location, and **the one entry whose service name cannot be guessed from the SDK.**
   *
   * The boto3 client is `geo-places` with a dash; the endpoint service is `geo.places` with a dot.
   * Worse, `client.meta.endpoint_url` reports `geo-places.us-east-1.amazonaws.com`, which does not
   * resolve at all — the request actually goes to `places.geo.us-east-1.amazonaws.com`, which is
   * what the endpoint's wildcard private DNS (`*.places.geo.us-east-1.amazonaws.com`) covers.
   *
   * A first pass grepping the service list for `geo-places` found nothing and concluded these tools
   * would need a NAT gateway. They do not. Verified by `dig` on both hostnames and by a `before-send`
   * hook on a live `geocode` call.
   */
  geoPlaces: { id: 'GeoPlacesEndpoint', serviceName: 'geo.places', usedBy: 'location tool' },
  geoRoutes: { id: 'GeoRoutesEndpoint', serviceName: 'geo.routes', usedBy: 'location tool' },

  /** Knowledge-base retrieval — `bedrock:Retrieve` from the knowledge tool. */
  bedrockAgentRuntime: {
    id: 'BedrockAgentRuntimeEndpoint',
    serviceName: 'bedrock-agent-runtime',
    usedBy: 'knowledge tool',
  },

  /**
   * How every tool reaches the backend, once the backend API is `PRIVATE`.
   *
   * The wildcard private DNS (`*.execute-api.us-east-1.amazonaws.com`) is what lets
   * `BACKEND_API_URL` stay exactly as it is — no tool's environment changes, and the URL in
   * `/multi-tenant-travel/backend/api-url` stays correct.
   */
  executeApi: {
    id: 'ExecuteApiEndpoint',
    serviceName: 'execute-api',
    usedBy: 'tool Lambdas → backend',
  },

  /** `AssumeRole` for the per-request tenant-scoped credentials the backend derives. */
  sts: { id: 'StsEndpoint', serviceName: 'sts', usedBy: 'backend tenant isolation' },

  /** Model inference, via the application inference profile. The agent's hot path. */
  bedrockRuntime: {
    id: 'BedrockRuntimeEndpoint',
    serviceName: 'bedrock-runtime',
    usedBy: 'agent runtime → model',
  },

  /**
   * SSM Parameter Store — and **the entry most easily missed, because its absence is silent.**
   *
   * The agent reads three parameters at cold start: the inference profile ARN and the guardrail's id
   * and version. All three reads are deliberately non-fatal (`log.warning`, then carry on), which is
   * right — a guardrail is a backstop and an unreachable parameter store should not take the agent
   * down. But it means an unreachable SSM in a VPC produces a *working* agent that is **unguarded and
   * whose model spend is unattributable**, with nothing but a warning in a log nobody is reading.
   *
   * That is a far worse failure than a crash, and it is exactly the kind a missing endpoint causes:
   * the DNS name resolves, so the SDK waits for a route that does not exist and eventually gives up.
   * Two carefully-built controls would quietly stop applying.
   */
  ssm: {
    id: 'SsmEndpoint',
    serviceName: 'ssm',
    usedBy: 'agent runtime → guardrail + profile config',
  },

  /**
   * AgentCore's data plane — and **two endpoints rather than one**, which tracing the memory
   * client is what revealed.
   *
   * `AgentCoreMemorySessionManager` holds *two* boto3 clients: `bedrock-agentcore` for the data
   * plane (events, retrieval — every turn) and `bedrock-agentcore-control` for the control plane
   * (resolving the memory and its strategies). An earlier count listed only the first, which would
   * have deployed cleanly and then failed at the first turn with a timeout rather than an error —
   * the worst kind of missing endpoint, because nothing says "DNS resolved to an address with no
   * route".
   */
  /**
   * CloudWatch Logs — **the runtime needs this, and the reasoning that said otherwise was about
   * Lambda.**
   *
   * The note above this map explains why fifteen VPC Lambdas need no `logs` endpoint: Lambda's
   * execution environment ships logs itself, on a path that never touches the function's ENI. That is
   * correct, and **it does not transfer to AgentCore Runtime, which is a container in *our* subnets.**
   * Its log delivery is ordinary egress from an isolated subnet, and with no endpoint it has nowhere
   * to go.
   *
   * The timeline is unambiguous, which is why this is a fix rather than a guess. Endpoints created
   * `21:48`; the runtime's log group received its **last event ever at `22:19`** — the pre-migration
   * container still running — and nothing since, across days of traffic including a 30-check
   * conversation suite that passed minutes before the group was found empty.
   *
   * **It cost a diagnosis, not just some logs.** A runtime request returned `424 Failed Dependency`
   * and directed the operator to CloudWatch — pointing at the one place guaranteed to be empty.
   * Every other endpoint here is justified by a failure it prevents; this one is justified by the
   * failures it lets you *see*, which is the argument the flow logs above already make.
   */
  logs: {
    id: 'LogsEndpoint',
    serviceName: 'logs',
    usedBy: 'agent runtime → CloudWatch Logs (a container in our subnets, unlike Lambda)',
  },

  /**
   * AgentCore's data plane — and **two endpoints rather than one**, which tracing the memory
   * client is what revealed.
   *
   * `AgentCoreMemorySessionManager` holds *two* boto3 clients: `bedrock-agentcore` for the data
   * plane (events, retrieval — every turn) and `bedrock-agentcore-control` for the control plane
   * (resolving the memory and its strategies). An earlier count listed only the first, which would
   * have deployed cleanly and then failed at the first turn with a timeout rather than an error —
   * the worst kind of missing endpoint, because nothing says "DNS resolved to an address with no
   * route".
   */
  bedrockAgentCore: {
    id: 'BedrockAgentCoreEndpoint',
    serviceName: 'bedrock-agentcore',
    usedBy: 'agent runtime → memory (data plane)',
  },
  bedrockAgentCoreControl: {
    id: 'BedrockAgentCoreControlEndpoint',
    serviceName: 'bedrock-agentcore-control',
    usedBy: 'agent runtime → memory (control plane)',
  },

  /**
   * The Gateway the agent calls its tools through.
   *
   * A separate service from `bedrock-agentcore`, with its own wildcard DNS
   * (`*.gateway.bedrock-agentcore.us-east-1.amazonaws.com`) matching the per-gateway hostname in
   * `GATEWAY_MCP_URL`.
   */
  bedrockAgentCoreGateway: {
    id: 'BedrockAgentCoreGatewayEndpoint',
    serviceName: 'bedrock-agentcore.gateway',
    usedBy: 'agent runtime → tools',
  },
};
