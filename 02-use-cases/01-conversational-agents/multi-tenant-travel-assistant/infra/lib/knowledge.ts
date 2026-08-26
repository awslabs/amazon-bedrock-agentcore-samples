import { CfnOutput, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3vectors from 'aws-cdk-lib/aws-s3vectors';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * Bump when an **immutable** index property changes.
 *
 * `nonFilterableMetadataKeys`, `dimension` and `distanceMetric` cannot be updated in place, so
 * a change means a new index — and because the knowledge base and data source are bound to the
 * index, they are replaced too. Naming them all with this suffix makes the replacement work:
 * CloudFormation creates the new set before deleting the old, which collides on any fixed name.
 *
 * After bumping, re-run the seed's document upload and start a fresh ingestion job.
 */
const INDEX_GENERATION = 'v2';

export interface KnowledgeProps {
  /** Bucket holding the policy documents and their `.metadata.json` sidecars. */
  readonly documentsBucket: s3.Bucket;
}

/**
 * The policy knowledge base: prose the structured policy record cannot hold.
 *
 * Answers the questions a schema cannot — city-specific cap exceptions, the approval chain
 * for a medical cabin exception, what to do when a conference has pushed every property above
 * the cap. That contrast is why the sample has both a policy API and a knowledge base;
 * without it, retrieval would only re-answer what `get_travel_policy` already returns.
 *
 * **Isolation is a per-tenant metadata filter on every retrieval**, not a knowledge base per
 * tenant. One index with `{"tenant_id": {"$eq": "globex"}}` is the shape that reaches
 * thousands of tenants; a KB each multiplies ingestion cost and management surface for the
 * same guarantee. The filter is built server-side from verified context — a tool that let the
 * model choose it would have no isolation at all.
 *
 * **S3 Vectors rather than OpenSearch Serverless.** It scales to zero, and a vector store
 * with idle provisioned capacity would contradict this sample's own cost argument.
 */
export class Knowledge extends Construct {
  public readonly knowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly dataSource: bedrock.CfnDataSource;

  constructor(scope: Construct, id: string, props: KnowledgeProps) {
    super(scope, id);

    const stack = Stack.of(this);
    const stackName = stack.stackName;

    // Titan Text Embeddings v2 at 1024 dimensions — the index `dimension` below must match
    // the model exactly, or ingestion fails with a shape error rather than a helpful message.
    const embeddingModelArn = `arn:aws:bedrock:${stack.region}::foundation-model/amazon.titan-embed-text-v2:0`;
    const embeddingDimension = 1024;

    const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
      vectorBucketName: `${stackName.toLowerCase()}-vectors-${stack.account}`,
    });
    vectorBucket.applyRemovalPolicy(RemovalPolicy.DESTROY);

    const index = new s3vectors.CfnIndex(this, 'PolicyIndex', {
      // Renaming this replaces the index, which is sometimes exactly what you want:
      // `nonFilterableMetadataKeys` is **immutable after creation**, so changing it means a
      // new index (and a re-sync), not an update.
      indexName: `policy-docs-${INDEX_GENERATION}`,
      vectorBucketName: vectorBucket.vectorBucketName!,
      dataType: 'float32',
      dimension: embeddingDimension,
      // Cosine for text embeddings: Titan vectors are normalised, so cosine and dot product
      // rank identically, and cosine is what the model card documents.
      distanceMetric: 'cosine',
      metadataConfiguration: {
        // **Required, and the reason is a 2048-byte cliff.** Every metadata key is filterable
        // by default, and Bedrock attaches the chunk's own text as metadata — so ingestion
        // fails with *"Filterable metadata must have at most 2048 bytes"* on any realistic
        // document. Declaring Bedrock's two internal keys non-filterable moves the bulk out
        // of the filterable budget while leaving our own fields (a few dozen bytes)
        // filterable.
        //
        // Note the inversion: this property lists what *cannot* be filtered. `tenant_id` is
        // deliberately absent, because listing it here would make the isolation field
        // unusable as a filter — the exact opposite of the intent.
        //
        // Verified directly against the S3 Vectors API: a 3000-byte `AMAZON_BEDROCK_TEXT`
        // value is accepted, and a `{"tenant_id": {"$eq": …}}` query still matches.
        nonFilterableMetadataKeys: ['AMAZON_BEDROCK_TEXT', 'AMAZON_BEDROCK_METADATA'],
      },
    });
    index.addDependency(vectorBucket);
    index.applyRemovalPolicy(RemovalPolicy.DESTROY);

    // The knowledge base reads documents and writes vectors, so it needs both sides.
    const role = new iam.Role(this, 'KnowledgeBaseRole', {
      roleName: `${stackName}-kb`,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com', {
        // Confused-deputy guards: without these, any account able to name our role ARN could
        // have Bedrock use it on their behalf.
        conditions: {
          StringEquals: { 'aws:SourceAccount': stack.account },
          ArnLike: {
            'aws:SourceArn': `arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/*`,
          },
        },
      }),
    });

    props.documentsBucket.grantRead(role);

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [embeddingModelArn],
      }),
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        // Ingestion writes vectors; retrieval queries them. `GetIndex` is needed because the
        // service validates the index's dimension before its first write.
        actions: [
          's3vectors:GetIndex',
          's3vectors:PutVectors',
          's3vectors:GetVectors',
          's3vectors:QueryVectors',
          's3vectors:ListVectors',
          's3vectors:DeleteVectors',
        ],
        resources: [vectorBucket.attrVectorBucketArn, `${vectorBucket.attrVectorBucketArn}/*`],
      }),
    );

    this.knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'PolicyKnowledgeBase', {
      // Versioned with the index, because replacing the index replaces the knowledge base —
      // and CloudFormation creates the replacement *before* deleting the old one, so a fixed
      // name collides with itself ("KnowledgeBase with name … already exists").
      name: `${stackName}-policy-${INDEX_GENERATION}`,
      description: 'Corporate travel policy prose, filtered per tenant on every retrieval',
      roleArn: role.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: { embeddingModelArn },
      },
      storageConfiguration: {
        type: 'S3_VECTORS',
        s3VectorsConfiguration: {
          vectorBucketArn: vectorBucket.attrVectorBucketArn,
          indexArn: index.attrIndexArn,
        },
      },
    });
    this.knowledgeBase.addDependency(index);
    // **The role's inline policy must exist before the knowledge base is created.**
    // Bedrock validates the storage configuration by actually calling `s3vectors:QueryVectors`
    // during creation, so a KB built while the policy is still pending fails with a 403 that
    // reads like a malformed storage config ("The knowledge base storage configuration
    // provided is invalid"). CDK does not infer this ordering, because the KB references the
    // role's ARN rather than its policy.
    if (role.node.tryFindChild('DefaultPolicy')) {
      this.knowledgeBase.node.addDependency(role.node.findChild('DefaultPolicy'));
    }
    this.knowledgeBase.applyRemovalPolicy(RemovalPolicy.DESTROY);

    this.dataSource = new bedrock.CfnDataSource(this, 'PolicyDocuments', {
      name: `${stackName}-policy-docs-${INDEX_GENERATION}`,
      knowledgeBaseId: this.knowledgeBase.attrKnowledgeBaseId,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: props.documentsBucket.bucketArn,
          // Only the policy prefix. The bucket may hold other things later, and an
          // unconstrained data source would ingest them silently.
          inclusionPrefixes: ['policy/'],
        },
      },
      // Documents outlive the stack's vectors: on teardown, delete the vectors rather than
      // leaving orphaned embeddings behind that a later KB would inherit.
      dataDeletionPolicy: 'DELETE',
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          // Fixed size with overlap, because the failure mode that matters here is a rule
          // separated from its exception: "hotels up to $250" retrieved without "except in
          // New York and San Francisco" is a confidently incomplete answer, which is worse
          // than no answer.
          //
          // Observed working as intended: the top chunk for "what if every hotel is over the
          // cap?" is ~2500 characters carrying *both* the city-specific caps and the
          // conference-inflation exception. It matters more here than it would elsewhere,
          // because a *direct* S3 Vectors index is **semantic-only** — hybrid (keyword +
          // vector) exists on S3 Vectors only through the OpenSearch `s3vector` engine, which
          // means running a provisioned OpenSearch cluster, i.e. giving up the scale-to-zero
          // property this store was chosen for. So there is no lexical fallback when a chunk
          // boundary splits a rule from its qualifier, and overlap has to do that work.
          //
          // Not yet compared against `SEMANTIC` chunking; worth measuring once the eval
          // harness can score retrieval rather than asserting a winner here.
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: { maxTokens: 500, overlapPercentage: 20 },
        },
      },
    });
    this.dataSource.addDependency(this.knowledgeBase);

    // Read by the retrieval tool. SSM rather than a CFN export: exports lock, and the tool is
    // deployed from a different app.
    new ssm.StringParameter(this, 'KnowledgeBaseIdParam', {
      parameterName: '/multi-tenant-travel/knowledge/knowledge-base-id',
      stringValue: this.knowledgeBase.attrKnowledgeBaseId,
      description: 'Bedrock knowledge base holding per-tenant policy prose',
    });

    new ssm.StringParameter(this, 'DataSourceIdParam', {
      parameterName: '/multi-tenant-travel/knowledge/data-source-id',
      stringValue: this.dataSource.attrDataSourceId,
      description: 'Data source to sync after uploading policy documents',
    });

    new CfnOutput(this, 'KnowledgeBaseId', {
      value: this.knowledgeBase.attrKnowledgeBaseId,
      description: 'Sync the data source after seeding, then query with a tenant filter',
    });
    new CfnOutput(this, 'DataSourceId', { value: this.dataSource.attrDataSourceId });
  }
}
