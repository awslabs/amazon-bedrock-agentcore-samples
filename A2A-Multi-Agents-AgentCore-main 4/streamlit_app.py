#!/usr/bin/env python3
"""
A2A Multi-Agent Communication Demo - Streamlit Interactive App

Interactive demo showcasing Agent-to-Agent (A2A) communication between 
monitoring and operations orchestrator agents using AWS Bedrock AgentCore.

Features:
- Home page with architecture overview
- Agent cards showing capabilities and skills  
- Interactive chat with A2A communication
- Bedrock AgentCore primitives visualization
"""

import streamlit as st
import json
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add the A2A directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'A2A'))
from a2a_communication_compliant import A2AService, TaskState

# Page configuration
st.set_page_config(
    page_title="a Multi-Agent Communication Demo",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_custom_css():
    """Load custom CSS for better styling"""
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .agent-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .skill-badge {
        background: #667eea;
        color: white;
        padding: 0.3rem 0.6rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.2rem;
        display: inline-block;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    
    .user-message {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    
    .agent-message {
        background: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    
    .bedrock-primitive {
        background: #fff3e0;
        border: 1px solid #ff9800;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'a2a_service' not in st.session_state:
        st.session_state.a2a_service = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'current_task' not in st.session_state:
        st.session_state.current_task = None
    if 'agents_health' not in st.session_state:
        st.session_state.agents_health = {}

def get_a2a_service():
    """Get or create A2A service instance"""
    if st.session_state.a2a_service is None:
        try:
            st.session_state.a2a_service = A2AService()
            return st.session_state.a2a_service
        except Exception as e:
            st.error(f"Failed to initialize A2A service: {str(e)}")
            return None
    return st.session_state.a2a_service

def home_page():
    """Render the home page with architecture overview"""
    st.markdown("""
    <div class="main-header">
        <h1>A2A Multi-Agent AgentCore Incident Response System</h1>
        <p>Agent2Agent Protocol with AWS Bedrock AgentCore</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Architecture Overview
    st.header("🏛️ System Architecture")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("A2A Protocol Components")
        st.markdown("""
        - **Agent Discovery**: Agent card-based capability discovery
        - **Task Lifecycle**: Structured task state management
        - **Message Flow**: JSON-RPC compliant bidirectional communication
        - **State Tracking**: Real-time task status monitoring
        - **Cross-Agent Coordination**: Incident response orchestration
        """)
        
        st.subheader("AWS Bedrock AgentCore Integration")
        st.markdown("""
        - **Runtime Management**: Agent runtime orchestration
        - **Streaming Responses**: Real-time agent communication
        - **Authentication**: AWS IAM-based security
        - **Scalability**: Serverless agent execution
        - **Monitoring**: Built-in observability
        """)
    
    with col2:
        st.subheader("Agent Ecosystem")
        
        # Monitoring Agent Overview
        st.markdown("""
        <div class="agent-card">
            <h4>🔍 Monitoring Agent (Strands)</h4>
            <p><strong>Purpose:</strong> CloudWatch monitoring and analysis</p>
            <p><strong>Capabilities:</strong> Log analysis, alarm monitoring, root cause analysis</p>
            <p><strong>Integration:</strong> AWS Bedrock AgentCore Runtime</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Operations Orchestrator Overview
        st.markdown("""
        <div class="agent-card">
            <h4>⚙️ Operations Orchestrator (OpenAI Multi-Agent)</h4>
            <p><strong>Purpose:</strong> Incident management and coordination</p>
            <p><strong>Capabilities:</strong> Jira/GitHub integration, team coordination</p>
            <p><strong>Integration:</strong> AWS Bedrock AgentCore Runtime</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Real-time System Status
    st.header("📊 System Status")
    
    a2a_service = get_a2a_service()
    if a2a_service:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>🟢</h3>
                <p><strong>A2A Service</strong></p>
                <p>Operational</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            agents_count = len(a2a_service.list_agents())
            st.markdown(f"""
            <div class="metric-card">
                <h3>{agents_count}</h3>
                <p><strong>Registered Agents</strong></p>
                <p>Available</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            tasks_count = len(a2a_service.tasks)
            st.markdown(f"""
            <div class="metric-card">
                <h3>{tasks_count}</h3>
                <p><strong>Active Tasks</strong></p>
                <p>In Session</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="metric-card">
                <h3>v1.0</h3>
                <p><strong>Protocol Version</strong></p>
                <p>A2A-1.0</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Bedrock AgentCore Primitives
    st.header("🧩 Bedrock AgentCore Primitives")
    
    # First row - Core Primitives
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>🏃‍♂️ Agent Runtime</h4>
            <ul>
                <li>Serverless execution environment</li>
                <li>Auto-scaling based on demand</li>
                <li>State management & lifecycle</li>
                <li>Resource isolation</li>
                <li>Container orchestration</li>
                <li>ARN-based invocation</li>
                <li>Local & remote deployment</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>🆔 Agent Identity</h4>
            <ul>
                <li>Agent card-based discovery</li>
                <li>Capability registration</li>
                <li>Skill & tool definitions</li>
                <li>A2A protocol compliance</li>
                <li>Provider metadata</li>
                <li>Integration declarations</li>
                <li>Version management</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>🧠 Memory Management</h4>
            <ul>
                <li>User preference strategies</li>
                <li>Semantic memory storage</li>
                <li>Session summaries</li>
                <li>Custom memory patterns</li>
                <li>Namespace isolation</li>
                <li>Cross-agent memory sharing</li>
                <li>Context persistence</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Second row - Advanced Primitives
    st.markdown("<br>", unsafe_allow_html=True)
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>📊 Agent Observability</h4>
            <ul>
                <li>Real-time health monitoring</li>
                <li>Task state tracking</li>
                <li>Performance metrics</li>
                <li>Error logging & analysis</li>
                <li>Streaming response tracking</li>
                <li>A2A protocol monitoring</li>
                <li>CloudWatch integration</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>🌐 Gateway & Integration</h4>
            <ul>
                <li>MCP gateway architecture</li>
                <li>OAuth2/JWT authentication</li>
                <li>Service orchestration</li>
                <li>Tool integration layer</li>
                <li>API gateway routing</li>
                <li>External system connectivity</li>
                <li>Secure proxy services</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
        <div class="bedrock-primitive">
            <h4>📡 Communication Layer</h4>
            <ul>
                <li>Streaming responses</li>
                <li>Message queuing</li>
                <li>A2A protocol compliance</li>
                <li>Error handling & retry</li>
                <li>JSON-RPC messaging</li>
                <li>Task lifecycle management</li>
                <li>Cross-agent coordination</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

def agents_page():
    """Render the agents page with detailed agent cards"""
    st.header("🤖 Agent Registry & Capabilities")
    
    a2a_service = get_a2a_service()
    if not a2a_service:
        st.error("A2A Service not available")
        return
    
    # Agent Health Check
    if st.button("🏥 Run Health Check"):
        with st.spinner("Checking agent health..."):
            try:
                health_status = asyncio.run(a2a_service.health_check())
                st.session_state.agents_health = health_status
                st.success("Health check completed!")
            except Exception as e:
                st.error(f"Health check failed: {str(e)}")
    
    # Display agents
    for agent_id in a2a_service.list_agents():
        agent_card = a2a_service.get_agent_card(agent_id)
        
        with st.expander(f"🤖 {agent_card.get('name', agent_id)}", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Description:** {agent_card.get('description', 'No description available')}")
                
                if 'provider' in agent_card:
                    st.markdown(f"**Provider:** {agent_card['provider'].get('organization', 'Unknown')}")
                
                st.markdown(f"**Version:** {agent_card.get('version', 'Unknown')}")
                
                # Capabilities
                if 'capabilities' in agent_card:
                    st.markdown("**Capabilities:**")
                    caps = agent_card['capabilities']
                    cap_list = []
                    if caps.get('streaming'): cap_list.append("Streaming")
                    if caps.get('pushNotifications'): cap_list.append("Push Notifications")
                    if caps.get('stateTransitionHistory'): cap_list.append("State History")
                    st.markdown(f"- {', '.join(cap_list)}")
            
            with col2:
                # Health Status
                if agent_id in st.session_state.agents_health.get('agents', {}):
                    health = st.session_state.agents_health['agents'][agent_id]
                    status_emoji = "✅" if health['healthy'] else "❌"
                    status_text = "Healthy" if health['healthy'] else "Unhealthy"
                    st.markdown(f"**Status:** {status_emoji} {status_text}")
                    
                    if not health['healthy'] and 'error' in health:
                        st.error(f"Error: {health['error']}")
                else:
                    st.markdown("**Status:** ⏳ Unknown")
            
            # Skills
            if 'skills' in agent_card:
                st.markdown("### 🛠️ Skills & Capabilities")
                
                for skill in agent_card['skills']:
                    with st.container():
                        st.markdown(f"**{skill['name']}**")
                        st.markdown(f"_{skill['description']}_")
                        
                        # Tags
                        if 'tags' in skill:
                            tags_html = ""
                            for tag in skill['tags']:
                                tags_html += f'<span class="skill-badge">{tag}</span>'
                            st.markdown(tags_html, unsafe_allow_html=True)
                        
                        # Related tools/operations
                        if 'relatedTools' in skill:
                            st.markdown(f"**Tools:** `{'`, `'.join(skill['relatedTools'])}`")
                        elif 'relatedOperations' in skill:
                            st.markdown(f"**Operations:** `{'`, `'.join(skill['relatedOperations'])}`")
                        
                        st.divider()
            
            # Integrations
            if 'integrations' in agent_card:
                st.markdown("### 🔗 Integrations")
                for platform, config in agent_card['integrations'].items():
                    st.markdown(f"**{platform.upper()}**")
                    st.markdown(f"- API Version: {config.get('apiVersion', 'Unknown')}")
                    st.markdown(f"- Operations: {len(config.get('supportedOperations', []))}")

def chat_page():
    """Render the interactive chat page"""
    st.header("💬 Interactive A2A Chat")
    
    a2a_service = get_a2a_service()
    if not a2a_service:
        st.error("A2A Service not available")
        return
    
    # Sidebar for routing information and task management
    with st.sidebar:
        st.subheader("🎛️ Chat Controls")
        
        # Intelligent routing status
        st.info("🧠 **Intelligent Routing Enabled**\n\nAgents are automatically selected based on your message content using LLM analysis.")
        
        # Routing examples
        with st.expander("💡 Routing Examples"):
            st.markdown("""
            **Monitoring Agent** handles:
            - CloudWatch metrics and logs
            - Performance analysis  
            - AWS service monitoring
            - Error rate investigations
            
            **Operations Orchestrator** handles:
            - JIRA ticket creation
            - GitHub issue management
            - Team notifications
            - Incident coordination
            
            *Example messages:*
            - "Check CPU usage on EC2 instances" → Monitoring
            - "Create a JIRA ticket for this issue" → Operations
            """)
        
        # Current task info
        if st.session_state.current_task:
            task = st.session_state.current_task
            st.subheader("📋 Current Task")
            st.markdown(f"**ID:** `{task['id'][:8]}...`")
            st.markdown(f"**Selected Agent:** {task['agent_id']}")
            st.markdown(f"**State:** {task['state']}")
            st.markdown(f"**Created:** {task['created_at'][:19]}")
            
            # Show routing reason if available
            if 'routing_reason' in task:
                st.markdown(f"**Routing Reason:** {task['routing_reason']}")
            
            if st.button("🗑️ Clear Task"):
                st.session_state.current_task = None
                st.rerun()
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        
        if st.button("🚨 Demo Incident Response"):
            demo_incident = {
                "id": "INC-DEMO-001",
                "summary": "Database performance degradation",
                "severity": "high",
                "affected_services": ["RDS", "Lambda", "API Gateway"],
                "user_impact": "Login failures for users",
                "detection_time": datetime.utcnow().isoformat()
            }
            
            with st.spinner("Coordinating incident response..."):
                try:
                    response = asyncio.run(a2a_service.coordinate_incident_response(demo_incident))
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "type": "incident_response",
                        "timestamp": datetime.now(),
                        "incident": demo_incident,
                        "response": response
                    })
                    st.success("Incident response coordinated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Incident response failed: {str(e)}")
    
    # Chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Chat history
        st.subheader("💬 Conversation History")
        
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                if message["type"] == "user_message":
                    st.markdown(f"""
                    <div class="chat-message user-message">
                        <strong>👤 You → {message['agent']}</strong><br>
                        <small>{message['timestamp'].strftime('%H:%M:%S')}</small><br>
                        {message['content']}
                    </div>
                    """, unsafe_allow_html=True)
                
                elif message["type"] == "agent_response":
                    st.markdown(f"""
                    <div class="chat-message agent-message">
                        <strong>🤖 {message['agent']} → You</strong><br>
                        <small>{message['timestamp'].strftime('%H:%M:%S')}</small><br>
                        {message['content'][:500]}{'...' if len(message['content']) > 500 else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if len(message['content']) > 500:
                        with st.expander("View full response"):
                            st.markdown(message['content'])
                
                elif message["type"] == "incident_response":
                    st.markdown("""
                    <div class="chat-message" style="background: #fff3cd; border-left: 4px solid #ffc107;">
                        <strong>🚨 Coordinated Incident Response</strong><br>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"Incident: {message['incident']['summary']}", expanded=True):
                        col_a, col_b = st.columns(2)
                        
                        with col_a:
                            st.markdown("**📊 Monitoring Analysis**")
                            monitoring_task = message['response']['monitoring_task']
                            st.markdown(f"Status: {monitoring_task['status']['state']}")
                            st.markdown(monitoring_task['analysis'][:300] + "...")
                        
                        with col_b:
                            st.markdown("**⚙️ Operations Coordination**")
                            ops_task = message['response']['ops_task']
                            st.markdown(f"Status: {ops_task['status']['state']}")
                            st.markdown(ops_task['coordination'][:300] + "...")
        
        # Message input
        st.subheader("✍️ Send Message")
        
        with st.form("chat_form", clear_on_submit=True):
            user_message = st.text_area(
                "Message:",
                placeholder="Enter your message (agent will be automatically selected)...",
                height=100
            )
            
            col_send, col_new = st.columns(2)
            
            with col_send:
                send_button = st.form_submit_button("📤 Send Message", use_container_width=True)
            
            with col_new:
                new_task_button = st.form_submit_button("🆕 New Task", use_container_width=True)
            
            if send_button and user_message:
                with st.spinner("🧠 Analyzing message and selecting optimal agent..."):
                    try:
                        # Use intelligent routing for new tasks or if requested
                        if not st.session_state.current_task or new_task_button:
                            # Use intelligent routing to create task
                            task = asyncio.run(a2a_service.create_task_with_intelligent_routing(user_message))
                            st.session_state.current_task = task
                            selected_agent = task["agent_id"]
                            
                            # Show routing decision
                            st.success(f"🎯 Intelligent routing selected: **{selected_agent}**")
                            
                            task_id = task["id"]
                        else:
                            task_id = st.session_state.current_task["id"]
                            selected_agent = st.session_state.current_task["agent_id"]
                        
                        # Send message
                        with st.spinner(f"Sending message to {selected_agent}..."):
                            result = asyncio.run(a2a_service.send_message(task_id, user_message))
                        
                        # Add to chat history
                        st.session_state.chat_history.append({
                            "type": "user_message",
                            "timestamp": datetime.now(),
                            "agent": selected_agent,
                            "content": user_message
                        })
                        
                        st.session_state.chat_history.append({
                            "type": "agent_response",
                            "timestamp": datetime.now(),
                            "agent": selected_agent,
                            "content": result["message"]["parts"][0]["content"]
                        })
                        
                        st.success("Message processed successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Failed to process message: {str(e)}")
    
    with col2:
        st.subheader("📈 Chat Statistics")
        
        total_messages = len(st.session_state.chat_history)
        user_messages = len([m for m in st.session_state.chat_history if m["type"] == "user_message"])
        agent_responses = len([m for m in st.session_state.chat_history if m["type"] == "agent_response"])
        
        st.metric("Total Messages", total_messages)
        st.metric("User Messages", user_messages)
        st.metric("Agent Responses", agent_responses)
        
        # Routing statistics
        st.subheader("🧠 Routing Statistics")
        
        agent_usage = {}
        for msg in st.session_state.chat_history:
            if msg["type"] == "user_message":
                agent = msg["agent"]
                agent_usage[agent] = agent_usage.get(agent, 0) + 1
        
        if agent_usage:
            for agent, count in agent_usage.items():
                st.metric(f"{agent}", count)
        else:
            st.write("No routing data yet")
        
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.session_state.current_task = None
            st.rerun()

def main():
    """Main Streamlit app"""
    load_custom_css()
    initialize_session_state()
    
    # Sidebar navigation
    with st.sidebar:
        st.title("🤖 A2A Demo")
        
        page = st.radio(
            "Navigate to:",
            ["🏠 Home", "🤖 Agents", "💬 Chat"],
            index=0
        )
        
        st.divider()
        
        # System info
        st.subheader("ℹ️ System Info")
        st.markdown("**Protocol:** A2A v1.0")
        st.markdown("**Platform:** AWS Bedrock")
        st.markdown("**Framework:** Streamlit")
        
        if st.session_state.a2a_service:
            st.markdown(f"**Session:** `{st.session_state.a2a_service.session_id[:12]}...`")
    
    # Route to appropriate page
    if page == "🏠 Home":
        home_page()
    elif page == "🤖 Agents":
        agents_page()
    elif page == "💬 Chat":
        chat_page()

if __name__ == "__main__":
    main()