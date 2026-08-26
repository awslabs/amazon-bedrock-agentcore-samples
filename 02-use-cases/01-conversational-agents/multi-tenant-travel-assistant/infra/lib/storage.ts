import { CfnOutput, Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Storage for the mock TMC.
 *
 * A construct rather than its own stack: it shares a lifecycle with the API in
 * front of it, so splitting them bought nothing and cost a cross-stack export.
 * Removing a reference to an in-use export deadlocks a deploy — the consumer has
 * to be updated first — and that failure recurs every time the wiring changes.
 * One stack, several constructs, keeps the file separation without the coupling.
 *
 * Every table is keyed on `TENANT#<id>` as the partition key. That is not a
 * naming convention — it is the isolation mechanism. The
 * Lambdas assume a role whose policy carries a `dynamodb:LeadingKeys` condition
 * pinned to one tenant's key, so IAM refuses a cross-tenant read before the
 * request reaches any data. Application-level checks can be argued around by a
 * prompt-injected agent; an IAM condition cannot.
 *
 * Because the key shape is load-bearing, it has to be right from the first
 * deployment: changing a partition key later means migrating every item.
 */
export class Storage extends Construct {
  public readonly tables: Record<string, dynamodb.Table>;
  public readonly policyDocsBucket: s3.Bucket;
  /**
   * S3 access logs for every bucket in the stack, plus CloudFront's.
   *
   * **Here rather than in `FrontendHosting` because this construct is built first**, and an
   * access-log destination has to exist before its sources. Three buckets share it — policy docs,
   * the audit trail and the SPA — which is also less to reason about than three log buckets.
   */
  public readonly logBucket: s3.Bucket;
  /**
   * Common prefix for every table name, e.g. `multi-tenant-travel`.
   *
   * A real string, never derived downstream by editing a table name: table names
   * are CloudFormation tokens at synth time, so `.replace()` on one silently
   * matches nothing and ships the wrong value.
   */
  public readonly tablePrefix: string;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Names come from the enclosing stack so they stay stable and predictable.
    const stackName = Stack.of(this).stackName;

    // A sample should cost nothing when idle and leave nothing behind on
    // cleanup, so: on-demand billing and DESTROY. Production would use RETAIN
    // and point-in-time recovery.
    const common = {
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
    };

    const travelers = new dynamodb.Table(this, 'Travelers', {
      ...common,
      tableName: `${stackName}-travelers`,
    });

    const trips = new dynamodb.Table(this, 'Trips', {
      ...common,
      tableName: `${stackName}-trips`,
    });
    // "Show me Priya's trips" is the common read, and it must stay inside one
    // tenant — so the traveler index is local to the tenant partition rather
    // than global. A GSI keyed only on traveler would allow a query that spans
    // tenants, which is exactly what the key design exists to prevent.
    trips.addLocalSecondaryIndex({
      indexName: 'by-traveler',
      sortKey: { name: 'traveler_id', type: dynamodb.AttributeType.STRING },
    });

    const bookings = new dynamodb.Table(this, 'Bookings', {
      ...common,
      tableName: `${stackName}-bookings`,
    });

    // Held offers expire on their own. TTL rather than a sweeper: an offer that
    // outlives its fare must not be bookable, and relying on a scheduled job to
    // notice would leave a window where it still is.
    const offers = new dynamodb.Table(this, 'Offers', {
      ...common,
      tableName: `${stackName}-offers`,
      timeToLiveAttribute: 'ttl',
    });

    const policies = new dynamodb.Table(this, 'Policies', {
      ...common,
      tableName: `${stackName}-policies`,
    });

    const tenantConfig = new dynamodb.Table(this, 'TenantConfig', {
      ...common,
      tableName: `${stackName}-tenant-config`,
    });

    this.tables = { travelers, trips, bookings, offers, policies, tenantConfig };
    this.tablePrefix = stackName;

    // Policy documents, laid out `policy/<tenant>/…` so the bucket mirrors the
    // isolation model and a per-tenant prefix condition is expressible later.
    // The knowledge base ingests from here.
    /**
     * The access-log destination for every other bucket here, and for CloudFront.
     *
     * **`OBJECT_WRITER` ownership is required, not relaxed.** CloudFront writes log objects with an
     * ACL, and S3's modern default (`BUCKET_OWNER_ENFORCED`) rejects ACLs — so log delivery silently
     * never starts. Public access stays fully blocked; the setting governs ACLs, not reachability.
     *
     * This bucket does not log its own access: S3 refuses a bucket that logs to itself, and a second
     * log bucket would only relocate the question. That is the one `AwsSolutions-S1` acknowledged,
     * scoped to this construct so the other two stay checked.
     */
    this.logBucket = new s3.Bucket(this, 'AccessLogs', {
      bucketName: `${stackName.toLowerCase()}-access-logs-${Stack.of(this).account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      objectOwnership: s3.ObjectOwnership.OBJECT_WRITER,
      // Access logs are diagnostic; CloudTrail remains the audit record. 90 days is long enough to
      // investigate and short enough that storage stays a rounding error.
      lifecycleRules: [{ expiration: Duration.days(90) }],
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.policyDocsBucket = new s3.Bucket(this, 'PolicyDocs', {
      bucketName: `${stackName.toLowerCase()}-policy-docs-${Stack.of(this).account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      // **The bucket where access logging earns its cost.** These are tenant policy documents,
      // presigned per request after an ownership check — so "who fetched which tenant's document"
      // is a question worth being able to answer independently of our own logs.
      serverAccessLogsBucket: this.logBucket,
      serverAccessLogsPrefix: 'policy-docs/',
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new CfnOutput(this, 'PolicyDocsBucketName', {
      value: this.policyDocsBucket.bucketName,
      description: 'Bucket holding per-tenant policy documents',
    });

    for (const [name, table] of Object.entries(this.tables)) {
      new CfnOutput(this, `${name}TableName`, { value: table.tableName });
    }
  }
}
