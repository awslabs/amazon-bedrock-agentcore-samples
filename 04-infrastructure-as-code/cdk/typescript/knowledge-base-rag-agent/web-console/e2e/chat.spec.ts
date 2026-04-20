import { test, expect } from '@playwright/test';

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await page.route('**/api/auth/**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, token: 'mock-token' }),
      });
    });

    // Mock chat API
    await page.route('**/api/chat/**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: 'This is a mock response from the AI assistant.',
          conversationId: 'mock-conversation-123',
        }),
      });
    });

    await page.goto('/chat');
  });

  test('should display chat interface', async ({ page }) => {
    await expect(page.locator('h1')).toContainText(/chat|conversation/i);
    await expect(page.locator('textarea, input[type="text"]')).toBeVisible();
    await expect(page.locator('button[type="submit"], button:has-text("Send")')).toBeVisible();
  });

  test('should send message and receive response', async ({ page }) => {
    const messageInput = page.locator('textarea, input[type="text"]').first();
    const sendButton = page.locator('button[type="submit"], button:has-text("Send")').first();

    // Type a message
    await messageInput.fill('Hello, how are you?');
    await sendButton.click();

    // Should show user message
    await expect(page.locator('text=Hello, how are you?')).toBeVisible();

    // Should show AI response
    await expect(page.locator('text=This is a mock response from the AI assistant.')).toBeVisible();

    // Input should be cleared
    await expect(messageInput).toHaveValue('');
  });

  test('should handle empty message submission', async ({ page }) => {
    const sendButton = page.locator('button[type="submit"], button:has-text("Send")').first();

    // Try to send empty message
    await sendButton.click();

    // Should not send empty message or show validation
    await expect(page.locator('text=/cannot be empty|required/i')).toBeVisible();
  });

  test('should display loading state during message sending', async ({ page }) => {
    // Add delay to API response
    await page.route('**/api/chat/**', route => {
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            response: 'Delayed response',
            conversationId: 'mock-conversation-123',
          }),
        });
      }, 1000);
    });

    const messageInput = page.locator('textarea, input[type="text"]').first();
    const sendButton = page.locator('button[type="submit"], button:has-text("Send")').first();

    await messageInput.fill('Test message');
    await sendButton.click();

    // Should show loading state
    await expect(page.locator('text=/sending|loading/i, [data-testid="loading"]')).toBeVisible();

    // Should hide loading state after response
    await expect(page.locator('text=Delayed response')).toBeVisible();
    await expect(
      page.locator('text=/sending|loading/i, [data-testid="loading"]')
    ).not.toBeVisible();
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Mock API error
    await page.route('**/api/chat/**', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' }),
      });
    });

    const messageInput = page.locator('textarea, input[type="text"]').first();
    const sendButton = page.locator('button[type="submit"], button:has-text("Send")').first();

    await messageInput.fill('Test message');
    await sendButton.click();

    // Should show error message
    await expect(page.locator('text=/error|failed|something went wrong/i')).toBeVisible();
  });

  test('should maintain conversation history', async ({ page }) => {
    const messageInput = page.locator('textarea, input[type="text"]').first();
    const sendButton = page.locator('button[type="submit"], button:has-text("Send")').first();

    // Send first message
    await messageInput.fill('First message');
    await sendButton.click();
    await expect(page.locator('text=First message')).toBeVisible();

    // Send second message
    await messageInput.fill('Second message');
    await sendButton.click();
    await expect(page.locator('text=Second message')).toBeVisible();

    // Both messages should be visible
    await expect(page.locator('text=First message')).toBeVisible();
    await expect(page.locator('text=Second message')).toBeVisible();
  });

  test('should be accessible', async ({ page }) => {
    // Check for proper ARIA labels and roles
    await expect(page.locator('textarea, input[type="text"]').first()).toHaveAttribute(
      'aria-label'
    );
    await expect(
      page.locator('button[type="submit"], button:has-text("Send")').first()
    ).toHaveAttribute('aria-label');

    // Check for proper heading structure
    await expect(page.locator('h1, h2, h3').first()).toBeVisible();

    // Check keyboard navigation
    await page.keyboard.press('Tab');
    await expect(page.locator('textarea, input[type="text"]').first()).toBeFocused();
  });
});
