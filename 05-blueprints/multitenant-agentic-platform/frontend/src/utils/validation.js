/**
 * Token limit validation utilities.
 * Extracted for testability.
 */

/**
 * Validate that a token limit value is a positive integer.
 * @param {string|number} value - The value to validate
 * @returns {{ valid: boolean, error: string }} Validation result
 */
export function validateTokenLimit(value) {
  if (value === null || value === undefined || value === '') {
    return { valid: false, error: 'Token limit is required for new tenants' };
  }
  
  const strValue = String(value).trim();
  
  // Check for decimal point
  if (strValue.includes('.')) {
    return { valid: false, error: 'Token limit must be a whole number' };
  }
  
  const num = parseInt(strValue, 10);
  
  if (isNaN(num)) {
    return { valid: false, error: 'Token limit must be a positive number' };
  }
  
  if (num <= 0) {
    return { valid: false, error: 'Token limit must be a positive number' };
  }
  
  return { valid: true, error: '' };
}

/**
 * Calculate usage percentage from total tokens and limit.
 * @param {number} totalTokens - Current total tokens used
 * @param {number|null} tokenLimit - Token limit (null means no limit)
 * @returns {number|null} Percentage or null if no limit
 */
export function calculateUsagePercentage(totalTokens, tokenLimit) {
  if (tokenLimit === null || tokenLimit === undefined || tokenLimit <= 0) {
    return null;
  }
  return (totalTokens / tokenLimit) * 100;
}

/**
 * Get color indicator for usage percentage.
 * @param {number|null} percentage - Usage percentage
 * @returns {string} Color name: 'danger', 'warning', 'success', or 'default'
 */
export function getUsageColor(percentage) {
  if (percentage === null) return 'default';
  if (percentage >= 100) return 'danger';
  if (percentage >= 80) return 'warning';
  return 'success';
}

/**
 * Calculate total cost from inference cost and infrastructure cost.
 * @param {number} inferenceCost - Cost from token usage
 * @param {number} infrastructureCost - Cost from AWS infrastructure
 * @returns {number} Total cost (inference + infrastructure)
 */
export function calculateTotalCost(inferenceCost, infrastructureCost) {
  const inference = Number(inferenceCost) || 0;
  const infra = Number(infrastructureCost) || 0;
  return inference + infra;
}

/**
 * Format cost value as USD with 6 decimal places.
 * @param {number} cost - Cost value
 * @returns {string} Formatted cost string (e.g., "$0.045678")
 */
export function formatCost(cost) {
  const numCost = Number(cost) || 0;
  return `$${numCost.toFixed(6)}`;
}

/**
 * Calculate total cost summary across all tenants.
 * @param {Array} tenantData - Array of tenant data with costs
 * @param {Array} infrastructureCosts - Array of infrastructure cost data
 * @returns {{ totalInference: number, totalInfrastructure: number, grandTotal: number }}
 */
export function calculateCostSummary(tenantData, infrastructureCosts) {
  let totalInference = 0;
  let totalInfrastructure = 0;
  
  // Calculate inference costs
  for (const item of tenantData) {
    if (item.aggregation_key?.startsWith('tenant:')) {
      const inputTokens = Number(item.input_tokens) || 0;
      const outputTokens = Number(item.output_tokens) || 0;
      const inferenceCost = Number(item.total_cost) || ((inputTokens * 0.003 / 1000) + (outputTokens * 0.015 / 1000));
      totalInference += inferenceCost;
    }
  }
  
  // Calculate infrastructure costs
  for (const item of infrastructureCosts) {
    totalInfrastructure += Number(item.infrastructure_cost) || 0;
  }
  
  return {
    totalInference,
    totalInfrastructure,
    grandTotal: totalInference + totalInfrastructure
  };
}
