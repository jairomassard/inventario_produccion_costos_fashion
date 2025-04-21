import axios from 'axios';


const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000', // Usa la variable de Vite
    timeout: 60000,
    headers: {
        'Content-Type': 'application/json',
    },
});



// Interceptor para agregar el token a cada solicitud
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token'); // Recuperar el token
        if (token) {
            // console.log(`DEBUG: Token en la solicitud: ${token}`);
            config.headers.Authorization = `Bearer ${token}`; // Agregar token al header
        }
        return config;
    },
    (error) => {
        console.error('Error en el interceptor de solicitud:', error);
        return Promise.reject(error);
    }
);

apiClient.interceptors.response.use(
    (response) => response, // Devuelve la respuesta directamente si no hay errores
    (error) => {
        console.error("Error en la respuesta de Axios:", error.response);

        if (error.response?.status === 401) {
            console.error('Error 401: No autorizado o sesión expirada.');
            localStorage.removeItem('token'); // Limpia el token si hay error 401
            window.location.href = '/login'; // Redirige al usuario al login
        } else if (error.response?.status === 403) {
            console.error('Error 403: Acceso prohibido.');
            alert('No tienes permisos para realizar esta acción.');
        } else if (error.response?.status === 500) {
            console.error('Error 500: Error interno del servidor.');
            alert('Ha ocurrido un problema. Intenta nuevamente más tarde.');
        } else if (error.response?.status === 400) {
            console.error('Error 400: Solicitud incorrecta.', error.response.data);
            alert(error.response?.data?.error || "Error en la solicitud. Verifica los datos enviados.");
        }

        return Promise.reject(error);
    }
);

export default apiClient;
