# Demo Instructions - Real Estate Multi-Agent System

Complete instructions for demonstrating the Real Estate Coordinator application.

## 🎯 Demo Overview

This demo showcases:
- **Multi-Agent Architecture**: Coordinator orchestrating specialized agents
- **A2A Protocol**: Industry-standard agent-to-agent communication
- **OAuth 2.0 Security**: Secure authentication with AWS Cognito
- **Professional UI**: Modern React interface with real-time chat
- **AWS Bedrock AgentCore**: Serverless agent deployment

## 📋 Pre-Demo Checklist

### ✅ Prerequisites Verified
- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] AWS CLI configured
- [ ] AgentCore CLI installed
- [ ] AWS account with appropriate permissions

### ✅ Agents Deployed
```bash
# Check if deployment_info.json exists
ls deployment_info.json

# If not, deploy agents:
python setup_cognito_automated.py
python deploy_agents_with_oauth.py
```

### ✅ Fresh OAuth Token
```bash
# Generate fresh token (valid for 60 minutes)
python get_fresh_token.py
```

## 🚀 Starting the Demo

### Step 1: Start Backend (Terminal 1)

```bash
./start-backend.sh
```

**Expected Output:**
```
======================================================================
Real Estate Coordinator - Backend API Server
======================================================================
🚀 Starting backend server...
API will be available at: http://localhost:5000
======================================================================
 * Running on http://0.0.0.0:5000
```

**Keep this terminal open!**

### Step 2: Start UI (Terminal 2)

```bash
./start-ui.sh
```

**Expected Output:**
```
======================================================================
Real Estate Coordinator - Starting UI Application
======================================================================
🚀 Starting React development server...
The UI will open at: http://localhost:3000
======================================================================
```

**Browser should automatically open to http://localhost:3000**

## 🎬 Demo Script

### Introduction (1 minute)

"I'm going to demonstrate a sample multi-agent system built on AWS Bedrock AgentCore. This system uses three AI agents that communicate using the A2A protocol with OAuth 2.0 security."

**Show Architecture:**
- Point to the UI (React frontend)
- Explain the backend API (Flask server handling OAuth)
- Describe the coordinator agent (orchestrates sub-agents)
- Mention the two specialist agents (search and booking)

### Demo 1: Property Search (2 minutes)

**Action:** Type in the chat:
```
Find apartments in New York under $4000
```

**What to Highlight:**
- Natural language understanding
- Coordinator routes request to Property Search Agent
- A2A protocol communication with OAuth
- Formatted response with property details
- Real-time streaming response

**Expected Response:**
```
I found a great apartment option for you in New York under $4000!

**Modern Downtown Apartment** (ID: PROP001)
- **Location:** New York, NY
- **Price:** $3,500/month
- **Bedrooms:** 2 | **Bathrooms:** 2
- **Size:** 1,200 sq ft
- **Amenities:** Gym, parking, doorman
```

### Demo 2: Property Details (1 minute)

**Action:** Type:
```
Show me details for property PROP003
```

**What to Highlight:**
- Coordinator understands the request
- Fetches specific property information
- Rich formatted response with emojis and structure

**Expected Response:**
```
Here are the details for **PROP003**:

**Luxury Penthouse** 
- 📍 Location: San Francisco, CA  
- 💰 Price: $8,500/month  
- ✅ Status: Available
...
```

### Demo 3: Property Booking (2 minutes)

**Action:** Type:
```
Book PROP001 for John Doe, email john@example.com, phone 555-1234, move-in 2025-12-01
```

**What to Highlight:**
- Coordinator extracts booking details
- Routes to Property Booking Agent
- Creates booking with confirmation
- Multi-agent coordination in action

**Expected Response:**
```
✅ Booking confirmed!

**Booking Details:**
- Booking ID: BOOK-XXXXX
- Property: PROP001 - Modern Downtown Apartment
- Tenant: John Doe
- Email: john@example.com
- Move-in Date: 2025-12-01
- Status: Confirmed
```

### Demo 4: Check Booking Status (1 minute)

**Action:** Type:
```
List all my bookings
```

**What to Highlight:**
- Coordinator queries booking agent
- Returns all bookings
- Shows system state management

### Demo 5: Complex Query (2 minutes)

**Action:** Type:
```
I need a 2-bedroom apartment in Seattle under $3000 with parking
```

**What to Highlight:**
- Natural language processing
- Multiple criteria extraction
- Intelligent filtering
- Conversational response

## 🎨 UI Features to Highlight

### Visual Elements
- **Connection Status**: Green dot showing backend connectivity
- **Message Bubbles**: User (purple) vs Agent (gray)
- **Typing Indicator**: Shows when agent is processing
- **Timestamps**: On each message
- **Markdown Support**: Bold, lists, formatting in responses
- **Quick Actions**: Pre-defined query buttons
- **Responsive Design**: Works on mobile/tablet/desktop

### Technical Features
- **Real-time Communication**: Async message handling
- **Auto-scroll**: Messages scroll into view
- **Error Handling**: Graceful error messages
- **Loading States**: Visual feedback during processing

## 🔧 Technical Deep Dive (Optional)

### Show Backend Logs (Terminal 1)

Point out:
- OAuth token loading
- A2A client creation
- Agent card fetching
- Message routing
- Response extraction

### Show Agent Configuration

```bash
# Show coordinator config
cat realestate_coordinator/.bedrock_agentcore.yaml

# Show OAuth configuration
cat deployment_info.json | python -m json.tool
```

### Show AgentCore Deployment

```bash
# List deployed agents
agentcore list

# Show agent logs
agentcore logs realestate_coordinator --tail 20
```

## 🐛 Troubleshooting During Demo

### Backend Not Responding
```bash
# Check backend health
curl http://localhost:5000/api/health

# Restart backend
# Ctrl+C in Terminal 1, then ./start-backend.sh
```

### Token Expired
```bash
# Generate fresh token
python get_fresh_token.py

# Restart backend
```

### UI Not Loading
```bash
# Check if port 3000 is available
lsof -ti:3000

# Restart UI
# Ctrl+C in Terminal 2, then ./start-ui.sh
```

## 📊 Key Metrics to Mention

- **Response Time**: ~5-10 seconds per query
- **Token Expiry**: 60 minutes (auto-refreshed)
- **Scalability**: AgentCore auto-scales based on load
- **Cost**: Pay-per-invocation + compute time
- **Availability**: 99.9% SLA from AWS

## 🎓 Q&A Preparation

### Common Questions

**Q: How does OAuth work here?**
A: We use Cognito with client credentials flow. The backend fetches tokens and includes them in A2A requests. Agents validate tokens using JWT authorizer.

**Q: Can you add more agents?**
A: Yes! Create a new agent directory, implement the logic, deploy with `agentcore launch`, and add it to the coordinator's tools.

**Q: How do agents communicate?**
A: Using the A2A (Agent-to-Agent) protocol - an industry standard for agent communication. It uses JSON-RPC over HTTPS with OAuth bearer tokens.

**Q: What happens if an agent fails?**
A: The coordinator handles errors gracefully and returns user-friendly messages. AgentCore provides automatic retries and failover.

**Q: Can this run in production?**
A: Yes! Agents are already deployed to AWS. For production UI/backend, deploy to Lambda, ECS, or App Runner. See DEPLOYMENT_GUIDE.md.

**Q: How much does it cost?**
A: Costs include: AgentCore runtime (pay-per-invocation), Claude model usage (per token), Cognito (free tier covers most use), CloudWatch logs (minimal).

## 🎬 Closing

"This demonstrates a sample multi-agent system with:
- Secure OAuth 2.0 authentication
- Industry-standard A2A protocol
- Serverless deployment on AWS
- Professional user interface
- Real-time agent coordination

The entire system is deployed on AWS Bedrock AgentCore and can scale automatically based on demand."

## 📝 Post-Demo

### Stop the Application
```bash
# Terminal 1 (Backend): Ctrl+C
# Terminal 2 (UI): Ctrl+C
```

### Share Resources
- GitHub repository
- README.md for setup instructions
- DEPLOYMENT_GUIDE.md for production deployment
- Architecture diagrams

## 🔗 Additional Resources

- **AWS Bedrock AgentCore**: https://aws.amazon.com/bedrock/
- **A2A Protocol**: Agent-to-Agent communication standard
- **Strands Framework**: Python agent framework
- **Project Repository**: [Your GitHub URL]

---

**Demo Duration:** 10-15 minutes
**Preparation Time:** 5 minutes
**Technical Level:** Intermediate to Advanced

**Good luck with your demo! 🚀**
