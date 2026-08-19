# ============================================================================
# Memory Initialization - Populate Memory with Activity Preferences
# ============================================================================

# Initialize memory with activity preferences after memory is created
resource "null_resource" "initialize_memory" {
  # Trigger re-initialization if memory ID changes
  triggers = {
    memory_id = aws_bedrockagentcore_memory.memory.id
    region    = data.aws_region.current.id
  }

  # Execute Python script to initialize memory
  provisioner "local-exec" {
    command     = "python3 ${path.module}/scripts/init-memory.py"
    working_dir = path.module

    environment = {
      MEMORY_ID  = aws_bedrockagentcore_memory.memory.id
      AWS_REGION = data.aws_region.current.id
    }
  }

  # Ensure memory exists before initialization
  depends_on = [
    aws_bedrockagentcore_memory.memory
  ]
}

# ============================================================================
# Outputs
# ============================================================================

output "memory_initialization_status" {
  description = "Status of memory initialization"
  value       = "Memory initialized with activity preferences"
  depends_on  = [null_resource.initialize_memory]
}
