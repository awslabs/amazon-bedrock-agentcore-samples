"""
DynamoDB Conversation Manager
Handles conversation persistence and retrieval with 15-minute TTL eviction
"""
import json
import boto3
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, table_name: str, region: str = "us-east-1"):
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        
        # Get TTL minutes from environment variable, default to 15 minutes
        self.ttl_minutes = int(os.environ.get('CONVERSATION_TTL_MINUTES', '15'))
        logger.info(f"ConversationManager initialized with {self.ttl_minutes}-minute TTL")
        
    def _calculate_ttl_timestamp(self) -> int:
        """Calculate TTL timestamp for DynamoDB (current time + TTL minutes)"""
        ttl_time = datetime.utcnow() + timedelta(minutes=self.ttl_minutes)
        return int(ttl_time.timestamp())
        
    async def get_conversation_history(self, conversation_id: str, max_messages: int = 50) -> List[Dict]:
        """Retrieve conversation history from DynamoDB"""
        try:
            response = self.table.get_item(
                Key={'conversation_id': conversation_id}
            )
            
            if 'Item' not in response:
                logger.info(f"No conversation found for ID: {conversation_id}")
                return []
            
            item = response['Item']
            
            # Check if item has expired (additional safety check)
            current_time = int(datetime.utcnow().timestamp())
            item_ttl = item.get('ttl', 0)
            
            if item_ttl > 0 and current_time > item_ttl:
                logger.info(f"Conversation {conversation_id} has expired (TTL: {item_ttl}, Current: {current_time})")
                # Optionally delete the expired item
                await self.delete_conversation(conversation_id)
                return []
            
            messages = json.loads(item.get('messages', '[]'))
            
            # Return last N messages to keep context manageable
            if len(messages) > max_messages:
                messages = messages[-max_messages:]
                logger.info(f"Trimmed conversation to last {max_messages} messages")
            
            logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
            
        except ClientError as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving conversation {conversation_id}: {str(e)}")
            return []
    
    async def save_conversation_history(self, conversation_id: str, messages: List[Dict]) -> bool:
        """Save conversation history to DynamoDB with 15-minute TTL"""
        try:
            # Keep only last 100 messages to prevent item size limits
            if len(messages) > 100:
                messages = messages[-100:]
            
            # Calculate TTL timestamp (15 minutes from now)
            ttl_timestamp = self._calculate_ttl_timestamp()
            
            # Prepare item for DynamoDB
            item = {
                'conversation_id': conversation_id,
                'messages': json.dumps(messages),
                'updated_at': datetime.utcnow().isoformat(),
                'message_count': len(messages),
                'ttl': ttl_timestamp,  # TTL in seconds since epoch
                'ttl_human_readable': datetime.fromtimestamp(ttl_timestamp).isoformat()  # For debugging
            }
            
            # Save to DynamoDB
            self.table.put_item(Item=item)
            
            logger.info(f"Saved {len(messages)} messages for conversation {conversation_id} with TTL: {item['ttl_human_readable']}")
            return True
            
        except ClientError as e:
            logger.error(f"Error saving conversation {conversation_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving conversation {conversation_id}: {str(e)}")
            return False
    
    async def add_message_to_conversation(self, conversation_id: str, role: str, content: str) -> bool:
        """Add a single message to conversation history with updated TTL"""
        try:
            # Get current history
            current_messages = await self.get_conversation_history(conversation_id)
            
            # Add new message
            new_message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            current_messages.append(new_message)
            
            # Save updated history (this will reset the TTL to 15 minutes from now)
            return await self.save_conversation_history(conversation_id, current_messages)
            
        except Exception as e:
            logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}")
            return False
    
    async def refresh_conversation_ttl(self, conversation_id: str) -> bool:
        """Refresh the TTL for an existing conversation (extend by 15 minutes)"""
        try:
            # Calculate new TTL timestamp
            new_ttl = self._calculate_ttl_timestamp()
            
            # Update only the TTL field
            response = self.table.update_item(
                Key={'conversation_id': conversation_id},
                UpdateExpression='SET #ttl = :ttl, #ttl_hr = :ttl_hr, #updated = :updated',
                ExpressionAttributeNames={
                    '#ttl': 'ttl',
                    '#ttl_hr': 'ttl_human_readable',
                    '#updated': 'updated_at'
                },
                ExpressionAttributeValues={
                    ':ttl': new_ttl,
                    ':ttl_hr': datetime.fromtimestamp(new_ttl).isoformat(),
                    ':updated': datetime.utcnow().isoformat()
                },
                ConditionExpression='attribute_exists(conversation_id)',
                ReturnValues='UPDATED_NEW'
            )
            
            logger.info(f"Refreshed TTL for conversation {conversation_id} to {datetime.fromtimestamp(new_ttl).isoformat()}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Conversation {conversation_id} does not exist, cannot refresh TTL")
            else:
                logger.error(f"Error refreshing TTL for conversation {conversation_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error refreshing TTL for conversation {conversation_id}: {str(e)}")
            return False
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from DynamoDB"""
        try:
            self.table.delete_item(
                Key={'conversation_id': conversation_id}
            )
            logger.info(f"Deleted conversation {conversation_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            return False
    
    async def get_conversation_metadata(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation metadata without full message history"""
        try:
            response = self.table.get_item(
                Key={'conversation_id': conversation_id},
                ProjectionExpression='conversation_id, updated_at, message_count, #ttl, ttl_human_readable',
                ExpressionAttributeNames={'#ttl': 'ttl'}
            )
            
            if 'Item' in response:
                item = response['Item']
                
                # Check if item has expired
                current_time = int(datetime.utcnow().timestamp())
                item_ttl = item.get('ttl', 0)
                
                if item_ttl > 0 and current_time > item_ttl:
                    logger.info(f"Conversation {conversation_id} metadata shows expired item")
                    return None
                
                return item
            return None
            
        except ClientError as e:
            logger.error(f"Error getting metadata for conversation {conversation_id}: {str(e)}")
            return None
    
    def get_ttl_info(self) -> Dict:
        """Get TTL configuration information"""
        return {
            'ttl_minutes': self.ttl_minutes,
            'ttl_seconds': self.ttl_minutes * 60,
            'description': f"Conversations expire after {self.ttl_minutes} minutes of inactivity"
        }
