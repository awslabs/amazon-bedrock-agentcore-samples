import axios, { AxiosRequestConfig } from 'axios';
import { fetchAuthSession } from 'aws-amplify/auth';

// Create an axios instance with default configuration
const api = axios.create({
  baseURL: process.env.API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
  // Add withCredentials to handle CORS with credentials
  withCredentials: true,
});

// Add request interceptor to add authentication token
api.interceptors.request.use(
  async config => {
    try {
      // Get the current authenticated user's session
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();

      if (token) {
        // Add the token to the Authorization header
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    } catch (_error) {
      // If there's no authenticated session, proceed without token
      return config;
    }
  },
  error => {
    return Promise.reject(error);
  }
);

// Helper functions for API requests
export const apiGet = async <T>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  try {
    const response = await api.get<T>(url, config);
    return response.data;
  } catch (error) {
    console.error(`Error fetching data from ${url}:`, error);
    throw error;
  }
};

export const apiPost = async <T>(
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  try {
    const response = await api.post<T>(url, data, config);
    return response.data;
  } catch (error) {
    console.error(`Error posting data to ${url}:`, error);
    throw error;
  }
};

export const apiPut = async <T>(
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  try {
    const response = await api.put<T>(url, data, config);
    return response.data;
  } catch (error) {
    console.error(`Error updating data at ${url}:`, error);
    throw error;
  }
};

export const apiDelete = async <T>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  try {
    const response = await api.delete<T>(url, config);
    return response.data;
  } catch (error) {
    console.error(`Error deleting data at ${url}:`, error);
    throw error;
  }
};

export default api;
