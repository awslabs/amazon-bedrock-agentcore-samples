export interface ProxyConfig {
  apiUrl: string;
  timeout?: number;
}

export class ProxyService {
  private config: ProxyConfig;

  constructor(config: ProxyConfig) {
    this.config = {
      timeout: 30000,
      ...config,
    };
  }

  async proxyRequest(path: string, options: RequestInit = {}): Promise<Response> {
    const url = `${this.config.apiUrl}${path}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }
}
