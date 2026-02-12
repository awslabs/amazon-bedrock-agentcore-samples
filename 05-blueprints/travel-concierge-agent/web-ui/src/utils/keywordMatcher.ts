/**
 * Flexible keyword matching utility for button generation
 * Checks if a message contains ALL required keywords in ANY order
 *
 * Example usage:
 *
 * ```typescript
 * // This will match:
 * // "add a new card" ✓
 * // "please add card" ✓
 * // "I want to add a payment card" ✓
 * // "card add now" ✓
 * // "onboard new card" ✓
 *
 * const matched = matchesAnyKeywordGroup("add a new card", BUTTON_KEYWORDS.ADD_CARD)
 * // matched = true
 * ```
 */

export interface KeywordGroup {
  // All keywords in this array must be present (in any order)
  all: string[]
  // At least one keyword from this array must be present
  any?: string[]
}

/**
 * Check if text contains all keywords from a group
 */
export const containsKeywords = (text: string, group: KeywordGroup): boolean => {
  const lowerText = text.toLowerCase()

  // Check if ALL required keywords are present
  const hasAllKeywords = group.all.every(keyword =>
    lowerText.includes(keyword.toLowerCase())
  )

  if (!hasAllKeywords) {
    return false
  }

  // If there are "any" keywords, at least one must be present
  if (group.any && group.any.length > 0) {
    const hasAnyKeyword = group.any.some(keyword =>
      lowerText.includes(keyword.toLowerCase())
    )
    return hasAnyKeyword
  }

  return true
}

/**
 * Check if text matches any of the keyword groups
 */
export const matchesAnyKeywordGroup = (text: string, groups: KeywordGroup[]): boolean => {
  return groups.some(group => containsKeywords(text, group))
}

/**
 * Predefined keyword groups for common button triggers
 */
export const BUTTON_KEYWORDS = {
  // Add Payment Card button triggers
  ADD_CARD: [
    { all: ['add', 'card'] },
    { all: ['add', 'payment'] },
    { all: ['onboard', 'card'] },
    { all: ['enroll', 'card'] },
    { all: ['new', 'card'] },
    { all: ['register', 'card'] },
    { all: ['setup', 'payment'] },
  ] as KeywordGroup[],

  // Confirm Purchase button triggers (agent response)
  CONFIRM_PURCHASE: [
    { all: ['confirm', 'purchase'] },
    { all: ['complete', 'purchase'] },
    { all: ['finalize', 'purchase'] },
    { all: ['proceed', 'purchase'] },
    { all: ['ready', 'purchase'] },
    { all: ['ready', 'complete'] },
    { all: ['checkout'] },
  ] as KeywordGroup[],

  // User purchase intent keywords (must come from user message)
  USER_PURCHASE_INTENT: [
    { all: ['buy'] },
    { all: ['purchase'] },
    { all: ['checkout'] },
    { all: ['proceed', 'checkout'] },
    { all: ['complete', 'order'] },
    { all: ['finalize', 'order'] },
    { all: ['pay', 'now'] },
    { all: ['confirm', 'order'] },
    { all: ['book', 'now'] },
    { all: ['i', 'want', 'buy'] },
    { all: ['i', 'want', 'purchase'] },
    { all: ['ready', 'buy'] },
    { all: ['ready', 'purchase'] },
  ] as KeywordGroup[],
}
