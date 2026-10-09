const LOCAL_API_BASE_URL = 'http://127.0.0.1:8000/api'
const PRODUCTION_API_BASE_URL = '/api'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (
  import.meta.env.PROD ? PRODUCTION_API_BASE_URL : LOCAL_API_BASE_URL
)