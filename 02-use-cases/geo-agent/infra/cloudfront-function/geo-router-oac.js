/**
 * Amazon CloudFront Function: routes AI bot requests to the GEO Lambda origin.
 *
 * Detects AI crawler User-Agents (GPTBot, ClaudeBot, etc.) and switches
 * the request origin to the GEO Lambda Function URL via OAC (SigV4).
 * Also supports manual testing via ?ua=genaibot querystring.
 */

import cf from 'cloudfront';

var AI_BOT_PATTERNS = [
  // OpenAI
  'gptbot',
  'oai-searchbot',
  'chatgpt-user',
  // Anthropic
  'claudebot',
  'claude-web',
  'claude-user',
  // Perplexity
  'perplexitybot',
  'perplexity-user',
  // Google
  'google-extended',
  'googleother',
  // Microsoft
  'bingbot',
  'copilot',
  // Meta
  'meta-externalagent',
  'facebookbot',
  // Apple
  'applebot',
  'applebot-extended',
  // Common AI crawlers
  'cohere-ai',
  'amazonbot',
  'bytespider',
  'ccbot',
  'diffbot',
  'youbot',
];

var GEO_ORIGIN_ID = 'geo-lambda-origin';

function handler(event) {
  var request = event.request;
  var userAgent = (request.headers['user-agent'] && request.headers['user-agent'].value) || '';
  var userAgentLower = userAgent.toLowerCase();

  var isAiBot = false;
  for (var i = 0; i < AI_BOT_PATTERNS.length; i++) {
    if (userAgentLower.indexOf(AI_BOT_PATTERNS[i]) !== -1) {
      isAiBot = true;
      break;
    }
  }

  // Allow testing via querystring: ?ua=genaibot
  if (!isAiBot && request.querystring && request.querystring.ua && request.querystring.ua.value === 'genaibot') {
    isAiBot = true;
  }

  if (isAiBot) {
    request.headers['x-geo-bot'] = { value: 'true' };
    request.headers['x-geo-bot-ua'] = { value: userAgent };
    request.headers['x-original-host'] = { value: request.headers['host'] ? request.headers['host'].value : '' };

    cf.selectRequestOriginById(GEO_ORIGIN_ID);
  }

  return request;
}
