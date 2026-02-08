import axios, { AxiosRequestConfig, AxiosError } from 'axios';
import { fetchAuthSession } from 'aws-amplify/auth';

// Maximum number of retries for API calls
const MAX_RETRIES = 3;

// Delay between retries in milliseconds
const RETRY_DELAY = 1000;

// Create a proxy service to handle CORS issues
class ProxyService {
  private baseUrl: string;
  private proxyUrl: string | null;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_API_ENDPOINT ||
      'https://6lno6r9ffk.execute-api.us-east-1.amazonaws.com/v1';
    this.proxyUrl = process.env.NEXT_PUBLIC_API_PROXY_ENDPOINT || null;

    // Validate the proxy URL if it exists
    if (this.proxyUrl) {
      try {
        // Test if the URL is valid
        new URL(this.proxyUrl);
      } catch (error) {
        console.error('Invalid proxy URL:', this.proxyUrl, error);
        this.proxyUrl = null;
      }
    }

    console.log('ProxyService initialized with:', {
      baseUrl: this.baseUrl,
      proxyUrl: this.proxyUrl || 'Not available',
    });
  }

  // Get authentication token
  private async getAuthToken(): Promise<string | null> {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.idToken?.toString() || null;
    } catch (error) {
      console.error('Error getting auth token:', error);
      return null;
    }
  }

  // Create headers with auth token
  private async createHeaders(): Promise<Record<string, string>> {
    const token = await this.getAuthToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  // Sleep function for retry delay
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Handle API errors
  private handleApiError(error: any, endpoint: string): never {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;

      if (axiosError.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        console.error(`API Error (${axiosError.response.status}):`, axiosError.response.data);
        throw new Error(
          `API Error (${axiosError.response.status}): ${JSON.stringify(axiosError.response.data)}`
        );
      } else if (axiosError.request) {
        // The request was made but no response was received
        console.error('API Error (No Response):', axiosError.request);
        throw new Error('Network error: No response received from server');
      } else {
        // Something happened in setting up the request that triggered an Error
        console.error('API Error (Request Setup):', axiosError.message);
        throw new Error(`Error setting up request: ${axiosError.message}`);
      }
    } else {
      // Non-Axios error
      console.error(`Error with ${endpoint}:`, error);
      throw new Error(`Unknown error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  // Make a request with retries
  private async makeRequest<T>(
    method: string,
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig,
    retries = 0
  ): Promise<T> {
    try {
      const headers = await this.createHeaders();

      // Fix double slash issue by ensuring only one slash between baseUrl and endpoint
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
      const url = `${this.baseUrl}${this.baseUrl.endsWith('/') ? '' : '/'}${cleanEndpoint}`;

      // Try direct request first
      try {
        const response = await axios.request<T>({
          method,
          url,
          data,
          headers: {
            ...headers,
            ...config?.headers,
          },
          ...config,
        });

        return response.data;
      } catch (error) {
        // If CORS error or other error, try using the built-in proxy API
        console.log(`Direct request failed, trying proxy for ${endpoint}:`, error);

        try {
          // Use the built-in fetch API with the proxy endpoint
          const proxyResponse = await fetch(`/api/proxy?url=${encodeURIComponent(endpoint)}`, {
            method,
            headers: {
              'Content-Type': 'application/json',
              ...(headers.Authorization ? { Authorization: headers.Authorization } : {}),
            },
            body: data ? JSON.stringify(data) : undefined,
          });

          if (!proxyResponse.ok) {
            throw new Error(`Proxy request failed with status ${proxyResponse.status}`);
          }

          return await proxyResponse.json();
        } catch (proxyError) {
          console.error('Proxy request failed:', proxyError);
          throw proxyError;
        }
      }
    } catch (error) {
      // Implement retry logic for certain errors
      if (
        retries < MAX_RETRIES &&
        axios.isAxiosError(error) &&
        (error.code === 'ECONNABORTED' ||
          error.code === 'ETIMEDOUT' ||
          (error.response && (error.response.status >= 500 || error.response.status === 429)))
      ) {
        console.log(`Retrying ${endpoint} (${retries + 1}/${MAX_RETRIES})...`);
        await this.sleep(RETRY_DELAY * Math.pow(2, retries));
        return this.makeRequest(method, endpoint, data, config, retries + 1);
      }

      return this.handleApiError(error, endpoint);
    }
  }

  // Make a GET request
  async get<T>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
    return this.makeRequest<T>('GET', endpoint, undefined, config);
  }

  // Make a POST request
  async post<T>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.makeRequest<T>('POST', endpoint, data, config);
  }

  // Make a PUT request
  async put<T>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.makeRequest<T>('PUT', endpoint, data, config);
  }

  // Make a DELETE request
  async delete<T>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
    return this.makeRequest<T>('DELETE', endpoint, undefined, config);
  }
}

// Create a singleton instance
const proxyService = new ProxyService();

export default proxyService;
