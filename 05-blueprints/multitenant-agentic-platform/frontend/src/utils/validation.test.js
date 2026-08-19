/**
 * Property-based tests for frontend validation utilities.
 * 
 * Feature: tenant-token-limits
 * Property 1: Token Limit Validation (Frontend)
 * Property 4: Usage Percentage Calculation
 * Property 5: Usage Percentage Color Coding
 * Validates: Requirements 1.4, 3.2, 3.4, 3.5
 */
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { validateTokenLimit, calculateUsagePercentage, getUsageColor } from './validation.js';

describe('Token Limit Validation (Property 1)', () => {
  /**
   * Property 1: Token Limit Validation (Frontend)
   * For any positive integer, validation should return valid: true.
   * Validates: Requirements 1.4
   */
  it('should accept any positive integer', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 10 ** 12 }), (value) => {
        const result = validateTokenLimit(value);
        expect(result.valid).toBe(true);
        expect(result.error).toBe('');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 1: Token Limit Validation (Frontend)
   * For any zero or negative integer, validation should return valid: false.
   * Validates: Requirements 1.4
   */
  it('should reject zero and negative integers', () => {
    fc.assert(
      fc.property(fc.integer({ max: 0 }), (value) => {
        const result = validateTokenLimit(value);
        expect(result.valid).toBe(false);
        expect(result.error).toBeTruthy();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 1: Token Limit Validation (Frontend)
   * For any string representation of a positive integer, validation should return valid: true.
   * Validates: Requirements 1.4
   */
  it('should accept string representations of positive integers', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 10 ** 12 }), (value) => {
        const result = validateTokenLimit(String(value));
        expect(result.valid).toBe(true);
        expect(result.error).toBe('');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 1: Token Limit Validation (Frontend)
   * For any non-integer decimal, validation should return valid: false.
   * Validates: Requirements 1.4
   */
  it('should reject decimal numbers', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.01, max: 10 ** 6, noNaN: true }).filter(x => !Number.isInteger(x)),
        (value) => {
          const result = validateTokenLimit(String(value));
          expect(result.valid).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Edge case tests
  it('should reject null', () => {
    const result = validateTokenLimit(null);
    expect(result.valid).toBe(false);
  });

  it('should reject undefined', () => {
    const result = validateTokenLimit(undefined);
    expect(result.valid).toBe(false);
  });

  it('should reject empty string', () => {
    const result = validateTokenLimit('');
    expect(result.valid).toBe(false);
  });

  it('should accept minimum valid value (1)', () => {
    const result = validateTokenLimit(1);
    expect(result.valid).toBe(true);
  });
});

describe('Usage Percentage Calculation (Property 4)', () => {
  /**
   * Property 4: Usage Percentage Calculation
   * For any valid usage and limit, percentage should equal (usage / limit) * 100.
   * Validates: Requirements 3.2
   */
  it('should calculate percentage correctly for any valid inputs', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 10 ** 9 }),
        fc.integer({ min: 1, max: 10 ** 9 }),
        (totalTokens, tokenLimit) => {
          const result = calculateUsagePercentage(totalTokens, tokenLimit);
          const expected = (totalTokens / tokenLimit) * 100;
          expect(result).toBeCloseTo(expected, 10);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 4: Usage Percentage Calculation
   * When limit is null/undefined/0, should return null.
   * Validates: Requirements 3.3
   */
  it('should return null when no limit is set', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 10 ** 9 }), (totalTokens) => {
        expect(calculateUsagePercentage(totalTokens, null)).toBe(null);
        expect(calculateUsagePercentage(totalTokens, undefined)).toBe(null);
        expect(calculateUsagePercentage(totalTokens, 0)).toBe(null);
      }),
      { numRuns: 100 }
    );
  });

  // Edge cases
  it('should return 0% when usage is 0', () => {
    expect(calculateUsagePercentage(0, 1000)).toBe(0);
  });

  it('should return 100% when usage equals limit', () => {
    expect(calculateUsagePercentage(1000, 1000)).toBe(100);
  });

  it('should return >100% when usage exceeds limit', () => {
    expect(calculateUsagePercentage(1500, 1000)).toBe(150);
  });
});

describe('Usage Percentage Color Coding (Property 5)', () => {
  /**
   * Property 5: Usage Percentage Color Coding
   * For any percentage < 80, should return 'success'.
   * Validates: Requirements 3.4, 3.5
   */
  it('should return success for percentages below 80', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 79.99, noNaN: true }), (percentage) => {
        expect(getUsageColor(percentage)).toBe('success');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 5: Usage Percentage Color Coding
   * For any percentage >= 80 and < 100, should return 'warning'.
   * Validates: Requirements 3.4
   */
  it('should return warning for percentages between 80 and 99.99', () => {
    fc.assert(
      fc.property(fc.double({ min: 80, max: 99.99, noNaN: true }), (percentage) => {
        expect(getUsageColor(percentage)).toBe('warning');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 5: Usage Percentage Color Coding
   * For any percentage >= 100, should return 'danger'.
   * Validates: Requirements 3.5
   */
  it('should return danger for percentages at or above 100', () => {
    fc.assert(
      fc.property(fc.double({ min: 100, max: 1000, noNaN: true }), (percentage) => {
        expect(getUsageColor(percentage)).toBe('danger');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 5: Usage Percentage Color Coding
   * For null percentage, should return 'default'.
   * Validates: Requirements 3.3
   */
  it('should return default for null percentage', () => {
    expect(getUsageColor(null)).toBe('default');
  });

  // Boundary tests
  it('should return success at 79.9%', () => {
    expect(getUsageColor(79.9)).toBe('success');
  });

  it('should return warning at exactly 80%', () => {
    expect(getUsageColor(80)).toBe('warning');
  });

  it('should return warning at 99.9%', () => {
    expect(getUsageColor(99.9)).toBe('warning');
  });

  it('should return danger at exactly 100%', () => {
    expect(getUsageColor(100)).toBe('danger');
  });
});

// ============================================================
// Infrastructure Cost Tests
// Feature: tenant-infrastructure-costs
// ============================================================

import { calculateTotalCost, formatCost, calculateCostSummary } from './validation.js';

describe('Total Cost Calculation (Property 4)', () => {
  /**
   * Property 4: Total Cost Calculation
   * For any inference and infrastructure cost pair, total should equal their sum.
   * Validates: Requirements 4.1, 4.2
   */
  it('should calculate total cost as sum of inference and infrastructure', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 10000, noNaN: true }),
        fc.double({ min: 0, max: 10000, noNaN: true }),
        (inferenceCost, infrastructureCost) => {
          const result = calculateTotalCost(inferenceCost, infrastructureCost);
          const expected = inferenceCost + infrastructureCost;
          expect(result).toBeCloseTo(expected, 10);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 4: Total Cost Calculation
   * When either cost is null/undefined, should treat as 0.
   * Validates: Requirements 4.1, 4.2
   */
  it('should handle null/undefined costs as zero', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 10000, noNaN: true }), (cost) => {
        expect(calculateTotalCost(cost, null)).toBeCloseTo(cost, 10);
        expect(calculateTotalCost(cost, undefined)).toBeCloseTo(cost, 10);
        expect(calculateTotalCost(null, cost)).toBeCloseTo(cost, 10);
        expect(calculateTotalCost(undefined, cost)).toBeCloseTo(cost, 10);
      }),
      { numRuns: 100 }
    );
  });

  // Edge cases
  it('should return 0 when both costs are 0', () => {
    expect(calculateTotalCost(0, 0)).toBe(0);
  });

  it('should return 0 when both costs are null', () => {
    expect(calculateTotalCost(null, null)).toBe(0);
  });
});

describe('Cost Formatting (Property 5)', () => {
  /**
   * Property 5: Cost Formatting
   * For any cost value, format should be "$X.XXXXXX" (6 decimal places).
   * Validates: Requirements 3.2, 4.3
   */
  it('should format costs with $ prefix and 6 decimal places', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 10000, noNaN: true }), (cost) => {
        const result = formatCost(cost);
        expect(result).toMatch(/^\$\d+\.\d{6}$/);
        expect(result.startsWith('$')).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Property 5: Cost Formatting
   * Formatted cost should preserve the value (within precision).
   * Validates: Requirements 3.2, 4.3
   */
  it('should preserve cost value in formatted string', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 10000, noNaN: true }), (cost) => {
        const result = formatCost(cost);
        const parsed = parseFloat(result.substring(1)); // Remove $ prefix
        expect(parsed).toBeCloseTo(cost, 6);
      }),
      { numRuns: 100 }
    );
  });

  // Edge cases
  it('should format 0 as $0.000000', () => {
    expect(formatCost(0)).toBe('$0.000000');
  });

  it('should format null as $0.000000', () => {
    expect(formatCost(null)).toBe('$0.000000');
  });

  it('should format undefined as $0.000000', () => {
    expect(formatCost(undefined)).toBe('$0.000000');
  });

  it('should format small values correctly', () => {
    expect(formatCost(0.000001)).toBe('$0.000001');
  });
});

describe('Cost Summary Calculation (Property 6)', () => {
  /**
   * Property 6: Cost Summary Calculation
   * Grand total should equal sum of all inference costs plus all infrastructure costs.
   * Validates: Requirements 4.5, 6.3
   */
  it('should calculate summary totals correctly', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            aggregation_key: fc.constant('tenant:test'),
            tenant_id: fc.string({ minLength: 1, maxLength: 20 }),
            input_tokens: fc.integer({ min: 0, max: 100000 }),
            output_tokens: fc.integer({ min: 0, max: 100000 }),
            total_cost: fc.double({ min: 0, max: 100, noNaN: true })
          }),
          { minLength: 0, maxLength: 10 }
        ),
        fc.array(
          fc.record({
            tenant_id: fc.string({ minLength: 1, maxLength: 20 }),
            infrastructure_cost: fc.double({ min: 0, max: 100, noNaN: true })
          }),
          { minLength: 0, maxLength: 10 }
        ),
        (tenantData, infraCosts) => {
          const result = calculateCostSummary(tenantData, infraCosts);
          
          // Verify grand total equals sum of components
          expect(result.grandTotal).toBeCloseTo(
            result.totalInference + result.totalInfrastructure,
            10
          );
          
          // Verify infrastructure total
          const expectedInfra = infraCosts.reduce(
            (sum, item) => sum + (Number(item.infrastructure_cost) || 0),
            0
          );
          expect(result.totalInfrastructure).toBeCloseTo(expectedInfra, 10);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Edge cases
  it('should return zeros for empty arrays', () => {
    const result = calculateCostSummary([], []);
    expect(result.totalInference).toBe(0);
    expect(result.totalInfrastructure).toBe(0);
    expect(result.grandTotal).toBe(0);
  });

  it('should handle tenants without infrastructure costs', () => {
    const tenantData = [
      { aggregation_key: 'tenant:test', tenant_id: 'test', total_cost: 1.5 }
    ];
    const result = calculateCostSummary(tenantData, []);
    expect(result.totalInference).toBe(1.5);
    expect(result.totalInfrastructure).toBe(0);
    expect(result.grandTotal).toBe(1.5);
  });
});
