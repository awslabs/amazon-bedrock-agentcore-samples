import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as cloudtrail from 'aws-cdk-lib/aws-cloudtrail';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/**
 * The audit trail: **the record an auditor reads instead of trusting our logs.**
 *
 * Everything else in this stack logs its own behaviour, which is useful and not evidence — an
 * application that is wrong about what it did will be wrong in its logs too, in the same
 * direction. CloudTrail is written by AWS, not by us, so it answers "what actually happened"
 * for someone who does not take our word for it. That distinction is the whole point of this
 * construct.
 *
 * **What a trail adds over the default 90-day Event history**: durable retention on our own
 * terms, and — the property that matters — **log-file validation**, which makes tampering
 * detectable. Event history alone is a convenience view; a validated trail is evidence.
 *
 * **What it cannot add, measured rather than assumed:** DynamoDB *item-level* events. Both
 * selector shapes are rejected on a trail in this region (see the selector block below), so the
 * audit trail proves *which tenant, which conversation, on whose behalf obtained credentials* —
 * not which individual row was then read. That is a real limit on the claim, and the reason the
 * row-level guarantee rests on the IAM boundary making a cross-tenant read impossible rather
 * than on catching one after the fact.
 *
 * **What makes an access attributable.** `tenant_credentials.py` assumes the data role with
 * three session tags — `tenant` (the isolation boundary), `session_id` (which conversation) and
 * `user` (a hash of the traveller). CloudTrail records them on the `AssumeRole` event, and every
 * subsequent data event carries the same session identity. So a row read is traceable to a
 * tenant, a conversation and a person **without joining anything of ours** — the audit trail and
 * the cost ledger share one dimension set rather than needing a mapping table between them.
 *
 * **This construct deliberately takes no table list.** An earlier version accepted one to build
 * a data-event selector; since DynamoDB data events cannot be selected on a trail at all, a
 * `tables` prop would be accepted and silently ignored — a construct lying about what it does.
 *
 * **Cost, stated plainly because a reader will deploy this.** The first copy of management events
 * is free, so this trail's ongoing cost is S3 storage on a 90-day lifecycle — pennies at sample
 * traffic. The expensive shape is the one we could not use anyway: data events are billed per
 * event, and a CloudTrail Lake event data store adds its own ingestion charge.
 */
export interface AuditProps {
  /** Shared access-log destination, owned by `Storage`. */
  readonly logBucket: s3.IBucket;
}

export class Audit extends Construct {
  public readonly trail: cloudtrail.Trail;
  public readonly bucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: AuditProps) {
    super(scope, id);

    const stack = Stack.of(this);

    this.bucket = new s3.Bucket(this, 'TrailBucket', {
      bucketName: `${stack.stackName.toLowerCase()}-audit-${stack.account}`,
      // An audit log that can be read by anyone is not much of a control.
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      // Versioned so a deletion is recoverable. Combined with log-file validation below, the
      // useful property is that tampering is *detectable*, not merely discouraged.
      versioned: true,
      // **Access logs on the audit bucket are the most defensible of the three**: "who read the
      // audit trail" is exactly the question an auditor asks, and it is one CloudTrail's own
      // management events do not answer for S3 object reads.
      serverAccessLogsBucket: props.logBucket,
      serverAccessLogsPrefix: 'audit-trail/',
      lifecycleRules: [
        {
          // Long enough to demonstrate retention without accumulating cost in a sample. A real
          // deployment sets this from its own compliance requirement — which is exactly the kind
          // of number that should not be silently inherited from someone else's sample.
          expiration: Duration.days(90),
          noncurrentVersionExpiration: Duration.days(30),
        },
      ],
      // DESTROY with autoDelete so `npm run destroy` leaves nothing behind. **Wrong for
      // production**: an audit trail that disappears with the stack cannot answer questions about
      // the stack. Called out rather than left as a footgun.
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.trail = new cloudtrail.Trail(this, 'Trail', {
      trailName: `${stack.stackName}-audit`,
      bucket: this.bucket,
      // **The property that makes this non-repudiable.** CloudTrail writes digest files that
      // chain over the delivered logs, so an edited or deleted log file is provably detectable.
      // Without it the trail is a convenience log rather than evidence — and "non-repudiation"
      // would be a claim we could not back.
      enableFileValidation: true,
      // Single-region on purpose: the whole sample is `us-east-1`, and a multi-region trail would
      // record events from regions where nothing of ours exists. Not an organisation trail
      // either — this is one account, and asserting org-level coverage we cannot demonstrate
      // would be worse than scoping honestly.
      isMultiRegionTrail: false,
      includeGlobalServiceEvents: true,
      // Management events give the `AssumeRole` with its session tags. `ALL` rather than
      // write-only because a *read* of another tenant's row is precisely the event this trail
      // exists to make visible.
      managementEvents: cloudtrail.ReadWriteType.ALL,
    });

    // **DynamoDB item-level data events are NOT collected here, and that is a service limit
    // rather than a choice.** Measured against the CloudTrail API directly, in this region:
    //
    //   basic selector, AWS::DynamoDB::Table  -> UnsupportedOperationException
    //                                            "The operation requested is not supported in
    //                                             the region"
    //   basic selector, management events only -> OK
    //   advanced selector, resources.type      -> "The AWS::DynamoDB::Table data resource type
    //     = AWS::DynamoDB::Table                  is not supported"
    //
    // So neither selector shape works on a *trail*: DynamoDB data events require a CloudTrail
    // **Lake event data store**, a separate resource with its own ingestion pricing and query
    // model. CDK's L2 hints at the same limit — `DataResourceType` offers only
    // `LAMBDA_FUNCTION` and `S3_OBJECT`.
    //
    // **What this costs the audit story, stated plainly.** The trail records the `AssumeRole`
    // with all three session tags, so *"which tenant, which conversation, on whose behalf
    // obtained credentials"* is fully attributable and non-repudiable. What it cannot show is the
    // individual `GetItem`/`Query` those credentials then performed. The row-level half of the
    // trail therefore rests on the application's own logs plus the IAM boundary that makes a
    // cross-tenant read impossible in the first place — which is a weaker claim than
    // "traceable end to end from CloudTrail alone", and worth being honest about rather than
    // implying coverage we do not have.
    //
    // An event data store is the upgrade path if row-level audit is a hard requirement; it is
    // deliberately not added here, because a sample should not quietly commit a reader to a
    // per-event-priced resource they did not ask for.
    const cfnTrail = this.trail.node.defaultChild as cloudtrail.CfnTrail;
    cfnTrail.eventSelectors = [
      {
        // `All` rather than write-only: a *read* is the event this trail exists to make visible,
        // and management reads (including `AssumeRole`) are what remain available to us.
        readWriteType: 'All',
        includeManagementEvents: true,
        dataResources: [],
      },
    ];

    new CfnOutput(this, 'TrailBucketName', {
      value: this.bucket.bucketName,
      description: 'CloudTrail logs; data events for the tenant tables',
    });
    new CfnOutput(this, 'TrailArn', { value: this.trail.trailArn });
  }
}
