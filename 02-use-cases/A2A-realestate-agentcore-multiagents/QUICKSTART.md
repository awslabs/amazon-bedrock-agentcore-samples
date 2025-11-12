# Quick Start Guide

Get the Real Estate Coordinator UI running in 5 minutes!

## Prerequisites Check

```bash
# Check Python
python3 --version  # Should be 3.8+

# Check Node.js
node --version     # Should be 16+

# Check AWS CLI
aws --version
aws sts get-caller-identity  # Should show your AWS account

# Check AgentCore CLI
agentcore --version
```

## Step 1: Deploy Agents (One-time setup)

```bash
cd A2A-realestate-agentcore-multiagents

# Setup Cognito OAuth (takes ~2 minutes)
python setup_cognito_automated.py

# Deploy all agents (takes ~5-10 minutes)
python deploy_agents_with_oauth.py
```

**Expected output:**
```
✅ Successfully deployed 3 agent(s):
  • property_search_agent
  • property_booking_agent
  • realestate_coordinator
```

## Step 2: Start UI

```bash
./start-ui.sh
```

**Expected output:**
```
🚀 Starting React development server...
The UI will open at: http://localhost:3000
```

Your browser should automatically open to `http://localhost:3000`

## Step 4: Try It Out!

In the web interface, try these queries:

1. **Search for properties:**
   ```
   Find apartments in New York under $4000
   ```

2. **Get property details:**
   ```
   Show me details for property PROP003
   ```

3. **Book a property:**
   ```
   Book PROP001 for John Doe, email john@example.com, phone 555-1234, move-in 2025-12-01
   ```

4. **Check bookings:**
   ```
   List all my bookings
   ```

## Troubleshooting

### "Backend server is not running"
Make sure you started the backend in Step 2. Check if it's running:
```bash
curl http://localhost:5000/api/health
```

### "OAuth token expired"
The backend auto-refreshes tokens, but if needed:
```bash
python get_fresh_token.py
```

### "deployment_info.json not found"
You need to deploy the agents first (Step 1).

### Port already in use
If port 3000 or 5000 is in use:
```bash
# Find and kill the process
lsof -ti:5000 | xargs kill -9  # For backend
lsof -ti:3000 | xargs kill -9  # For UI
```

## What's Next?

- Read the full [README.md](README.md) for detailed documentation
- Explore the agent code in `realestate_coordinator/agent.py`
- Customize the UI in `ui/src/`
- Add more agents or modify existing ones

## Stopping the Application

1. Press `Ctrl+C` in the UI terminal
2. Press `Ctrl+C` in the backend terminal

## Restarting

Just run the start scripts again:
```bash
# Terminal 1
./start-backend.sh

# Terminal 2
./start-ui.sh
```

The agents remain deployed in AWS, so you don't need to redeploy them!

---

**Need help?** Check the [README.md](README.md) troubleshooting section.
