import { DynamoDBClient, QueryCommand } from "@aws-sdk/client-dynamodb";
import { createAwsClient } from "./AwsAuth";

/**
 * Query media assets from DynamoDB
 *
 * @param {string} uuid - The UUID to query
 * @returns {Promise<Array>} - The media assets
 */
export const getMediaAssets = async (uuid = "", assistantConfig = {}) => {
  let mediaAssets = [];
  try {
    // Create DynamoDB client with region from assistant config
    const dbRegion = assistantConfig.database?.region;
    const clientOptions = dbRegion ? { region: dbRegion } : {};
    const dynamodb = await createAwsClient(DynamoDBClient, clientOptions);

    const tableName = assistantConfig.database?.tableName;

    const input = {
      TableName: tableName,
      KeyConditionExpression: "prompt_id = :uuid",
      ExpressionAttributeValues: {
        ":uuid": {
          S: uuid,
        },
      },
      ScanIndexForward: false,
      ConsistentRead: true,
    };

    console.log("🤖 Calling Get Media Assets:");
    console.log("⚙️ Assistant Config:", assistantConfig);
    console.log("🌍 Database Region:", assistantConfig.database?.region || "default");
    console.log("📋 DynamoDB Input:", input);

    const command = new QueryCommand(input);
    const response = await dynamodb.send(command);

    console.log("📊 DynamoDB Response:", response);

    // Process actual DynamoDB responses if available
    if (response.hasOwnProperty("Items") && response.Items.length > 0) {
      for (let i = 0; i < response.Items.length; i++) {
        const item = response.Items[i];

        // Handle s3_uri format with presigned URL
        if (item.s3_uri && item.s3_uri.S) {
          try {
            // Parse the JSON string from s3_uri
            const s3UriData = JSON.parse(item.s3_uri.S);
            const presignedUrl = s3UriData.url;

            const timestamp = item.timestamp?.N || item.timestamp?.S || `Analysis ${i + 1}`;
            const promptId = item.prompt_id?.S || 'unknown-prompt';

            // Determine if it's a video or image based on URL
            const isVideo = presignedUrl.includes('.mp4') || presignedUrl.includes('.mov') || presignedUrl.includes('.avi');

            const mediaAsset = {
              agent_response: isVideo
                ? `I've analyzed the security camera video and detected activities. This analysis was captured at timestamp ${timestamp}.`
                : `I've analyzed the security camera frame and detected objects with bounding box annotations. This analysis was captured at timestamp ${timestamp}.`,
              user_question: isVideo ? "Analyze the security camera video" : "Analyze the security camera frame for object detection",
              tool_name: isVideo ? "video_analysis" : "frame_analysis",
              prompt_id: promptId,
              timestamp: timestamp,
            };

            if (isVideo) {
              mediaAsset.video = {
                title: `Security Video Analysis - ${new Date(parseInt(timestamp) * 1000).toLocaleString()}`,
                description: "Real-time smart home security camera video analysis with activity detection and event monitoring.",
                sources: [
                  {
                    src: presignedUrl,
                    type: "video/mp4",
                    thumbnail: ""
                  }
                ]
              };
            } else {
              mediaAsset.image = {
                title: `Security Frame Analysis - ${new Date(parseInt(timestamp) * 1000).toLocaleString()}`,
                description: "Real-time smart home security camera analysis with object detection, bounding boxes, and confidence scores for identified objects in the monitored environment.",
                src: presignedUrl,
                alt: "Security camera frame with object detection and bounding box overlays"
              };
            }

            mediaAssets.push(mediaAsset);
          } catch (parseError) {
            console.error("Error parsing s3_uri JSON:", parseError);
          }
        }
      }
    }

    if (mediaAssets.length > 0) {
      return mediaAssets;
    } else {
      return false;
    }


  } catch (error) {
    console.error("Error querying media assets:", error);
    throw error;
  }
};


