import { toast, ToastOptions } from 'react-toastify'

/**
 * Toast utility with consistent 15 second duration for all notifications
 */

const defaultOptions: ToastOptions = {
  position: 'top-right',
  autoClose: 15000, // 15 seconds
  hideProgressBar: false,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: true
}

export const showToast = {
  error: (message: string, options?: ToastOptions) => {
    toast.error(message, { ...defaultOptions, ...options })
  },

  success: (message: string, options?: ToastOptions) => {
    toast.success(message, { ...defaultOptions, ...options })
  },

  info: (message: string, options?: ToastOptions) => {
    toast.info(message, { ...defaultOptions, ...options })
  },

  warning: (message: string, options?: ToastOptions) => {
    toast.warning(message, { ...defaultOptions, ...options })
  }
}
