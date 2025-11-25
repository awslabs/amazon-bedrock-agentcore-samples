"""
Flask web application for slide deck agent demo - comparing basic vs memory-enabled agents
"""

import logging
import os
import sys
import traceback
from datetime import datetime

from agents.basic_agent import BasicSlideDeckAgent
from agents.memory_agent import MemoryEnabledSlideDeckAgent
from config import (
    DEFAULT_USER_ID,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_SECRET_KEY,
    OUTPUT_DIR,
    get_session_id,
)
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_cors import CORS
from memory_setup import setup_slide_deck_memory

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder="../templates", static_folder="../static")

# Security: Require secret key in production


if not FLASK_SECRET_KEY:
    import secrets
    logger.warning("⚠️  FLASK_SECRET_KEY not set - generating random key for this session")
    app.config["SECRET_KEY"] = secrets.token_hex(32)
else:
    app.config["SECRET_KEY"] = FLASK_SECRET_KEY

CORS(app)

# Global variables for demo
basic_agent = None
memory_agent = None
memory_session = None
memory_session_manager = None


def initialize_agents():
    """Initialize both basic and memory-enabled agents"""
    global basic_agent, memory_agent, memory_session, memory_session_manager

    try:
        # Initialize basic agent
        basic_agent = BasicSlideDeckAgent(OUTPUT_DIR)
        logger.info("✅ Basic agent initialized")

        # Initialize memory system and memory-enabled agent
        memory, session_manager, memory_mgr = setup_slide_deck_memory()
        memory_session_manager = session_manager  # Store globally for delete operations
        memory_session = session_manager.create_memory_session(
            actor_id=DEFAULT_USER_ID, session_id=get_session_id()
        )
        memory_agent = MemoryEnabledSlideDeckAgent(memory_session, OUTPUT_DIR)
        logger.info("✅ Memory-enabled agent initialized")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize agents: {e}")
        logger.error(traceback.format_exc())
        return False


@app.route("/")
def index():
    """Main page showing agent comparison"""
    return render_template("index.html")


@app.route("/create-basic", methods=["GET", "POST"])
def create_basic():
    """Create presentation using basic agent (no memory)"""
    if request.method == "GET":
        return render_template("create_basic.html")

    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "Please provide a presentation request"}), 400

        # Use basic agent
        logger.info(f"Processing basic request: {user_request[:100]}...")
        result = basic_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "result": result,
                "agent_type": "Basic Agent (No Memory)",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in basic creation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/create-memory", methods=["GET", "POST"])
def create_memory():
    """Create presentation using memory-enabled agent"""
    if request.method == "GET":
        return render_template("create_memory.html")

    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "Please provide a presentation request"}), 400

        # Use memory-enabled agent
        logger.info(f"Processing memory-enabled request: {user_request[:100]}...")
        result = memory_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "result": result,
                "agent_type": "Memory-Enabled Agent",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in memory-enabled creation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/compare")
def compare():
    """Side-by-side comparison page"""
    return render_template("compare.html")


@app.route("/compare-agents", methods=["POST"])
def compare_agents():
    """Compare both agents with the same request"""
    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "Please provide a presentation request"}), 400

        # Process with both agents
        logger.info(f"Comparing agents for request: {user_request[:100]}...")

        # Basic agent result
        basic_result = basic_agent.create_presentation(user_request)

        # Memory-enabled agent result
        memory_result = memory_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "basic_result": {
                    "result": basic_result,
                    "agent_type": "Basic Agent (No Memory)",
                    "description": "Creates presentations using default settings and basic styling options.",
                },
                "memory_result": {
                    "result": memory_result,
                    "agent_type": "Memory-Enabled Agent",
                    "description": "Learns your preferences and creates personalized presentations that improve over time.",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error in agent comparison: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/get-preferences")
def get_preferences():
    """Get current user preferences from memory"""
    try:
        if memory_agent:
            # Use the memory agent's preference tool
            preferences = memory_agent.get_user_preferences_tool()
            return jsonify({"success": True, "preferences": preferences})
        else:
            return jsonify({"error": "Memory agent not available"}), 500

    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/recommend-style", methods=["POST"])
def recommend_style():
    """Get style recommendations from memory agent"""
    try:
        data = request.get_json()
        topic = data.get("topic", "")
        audience = data.get("audience", "general")
        context = data.get("context", "business")

        if not topic:
            return jsonify({"error": "Please provide a presentation topic"}), 400

        if memory_agent:
            recommendations = memory_agent.recommend_style_tool(
                topic, audience, context
            )
            return jsonify({"success": True, "recommendations": recommendations})
        else:
            return jsonify({"error": "Memory agent not available"}), 500

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/delete-memory", methods=["POST"])
def delete_memory():
    """Delete all user preferences from memory using AgentCore Memory deletion APIs"""
    try:
        if memory_session_manager and memory_agent and memory_session:
            # Get the user namespace for preferences
            user_id = DEFAULT_USER_ID
            namespace = f"slidedecks/user/{user_id}/style_preferences"

            logger.info(f"🗑️ Searching for memory records in namespace: {namespace}")

            # First, search for all memory records in the user preference namespace
            # Use a broad query to find all preference records
            preference_memories = memory_session.search_long_term_memories(
                query="style preferences",  # Broad query to find all preferences
                namespace_prefix=namespace,
                top_k=100,  # Get up to 100 records to delete
            )

            if not preference_memories:
                logger.info("No memory records found to delete")
                return jsonify(
                    {
                        "success": True,
                        "message": "No preference records found to delete. Memory is already clear!",
                        "details": {"deleted": 0, "failed": 0, "namespace": namespace},
                    }
                )

            logger.info(f"Found {len(preference_memories)} memory records to delete")

            # Delete each memory record individually
            successful_count = 0
            failed_count = 0
            deleted_ids = []

            for memory_record in preference_memories:
                try:
                    # Extract the memory record ID - the correct field name is 'memoryRecordId'
                    record_id = memory_record.get("memoryRecordId")

                    if record_id:
                        # Use the memory session to delete the record
                        # The memory session should have a delete method
                        if hasattr(memory_session, "delete_memory_record"):
                            memory_session.delete_memory_record(record_id)
                        elif hasattr(memory_session_manager, "delete_memory_record"):
                            # Get the memory ID from our setup
                            memory_id = getattr(
                                memory_session,
                                "_memory_id",
                                "SlideDeckAgentMemory-rMV28tDfXu",
                            )
                            memory_session_manager.delete_memory_record(
                                memory_id=memory_id, memory_record_id=record_id
                            )
                        else:
                            logger.warning(
                                f"No delete method found, record ID: {record_id}"
                            )
                            failed_count += 1
                            continue

                        successful_count += 1
                        deleted_ids.append(record_id)
                        logger.info(f"✅ Deleted memory record: {record_id}")
                    else:
                        logger.warning(
                            f"No valid ID found in memory record: {list(memory_record.keys())}"
                        )
                        failed_count += 1

                except Exception as delete_error:
                    logger.error(f"❌ Failed to delete memory record: {delete_error}")
                    failed_count += 1

            logger.info(
                f"✅ Successfully deleted {successful_count} memory records for user {user_id}"
            )
            if failed_count > 0:
                logger.warning(f"⚠️ Failed to delete {failed_count} records")

            return jsonify(
                {
                    "success": True,
                    "message": (
                        f"Successfully deleted {successful_count} preference records! "
                        "The agent will start learning fresh."
                    ),
                    "details": {
                        "deleted": successful_count,
                        "failed": failed_count,
                        "namespace": namespace,
                        "deleted_ids": deleted_ids[
                            :5
                        ],  # Show first 5 IDs for reference
                    },
                }
            )
        else:
            return jsonify({"error": "Memory system not available"}), 500

    except Exception as e:
        logger.error(f"❌ Error deleting memory records: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/files")
def list_files():
    """List generated presentation files"""
    try:
        files = []
        if os.path.exists(OUTPUT_DIR):
            for filename in os.listdir(OUTPUT_DIR):
                if filename.endswith(".html"):  # Only show HTML files
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    file_info = {
                        "name": filename,
                        "size": os.path.getsize(filepath),
                        "modified": datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        ).isoformat(),
                        "type": "HTML Presentation",
                        "agent_type": (
                            "Memory Agent" if "_Memory" in filename else "Basic Agent"
                        ),
                    }
                    files.append(file_info)

        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)

        return jsonify({"success": True, "files": files})

    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download_file(filename):
    """Download a generated file"""
    try:
        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "Invalid filename"}), 400
        
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            flash(f"File {filename} not found", "error")
            return redirect(url_for("index"))

        return send_file(filepath, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/preview/<filename>")
def preview_file(filename):
    """Preview an HTML presentation file"""
    try:
        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "Invalid filename"}), 400
        
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath) or not filename.endswith(".html"):
            return jsonify({"error": f"HTML file {filename} not found"}), 404

        return send_file(filepath, mimetype="text/html")

    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "basic_agent": basic_agent is not None,
            "memory_agent": memory_agent is not None,
            "memory_session": memory_session is not None,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found", code=404), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", error="Internal server error", code=500), 500


def create_app():
    """Application factory pattern"""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initialize agents
    if not initialize_agents():
        logger.error("❌ Failed to initialize agents - some features may not work")

    return app


if __name__ == "__main__":
    # Create and run the app
    app = create_app()
    logger.info(f"🚀 Starting Slide Deck Demo Server on {FLASK_HOST}:{FLASK_PORT}")
    logger.info(f"📁 Output directory: {OUTPUT_DIR}")
    logger.info("🎯 Demo Features:")
    logger.info("   - Basic Agent (no memory)")
    logger.info("   - Memory-Enabled Agent (learns preferences)")
    logger.info("   - Side-by-side comparison")
    logger.info("   - HTML and PowerPoint generation")
    logger.info("   - File download and preview")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
