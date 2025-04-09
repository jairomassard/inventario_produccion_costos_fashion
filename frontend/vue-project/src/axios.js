// axios.js
import axios from '@/axios';

const instance = axios.create({
  baseURL: 'http://127.0.0.1:5000',
  timeout: 5000,
});

// Interceptor para agregar el token a las solicitudes
instance.interceptors.request.use(
  (config) => {
    // No agregar token en solicitudes preflight
    if (config.method !== 'options') {
      const token = localStorage.getItem('token');
      if (token) {
        console.log(`DEBUG: Token en la solicitud: ${token}`);
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default instance;

