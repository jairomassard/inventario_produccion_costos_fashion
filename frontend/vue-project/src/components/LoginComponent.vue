<template>
  <div id="login">
    <div class="login-wrapper">
      <div class="login-container">
        <!-- Logo del cliente -->
        <div class="logo-container">
          <img src="/images/logo.jpg" alt="Logo del cliente" class="logo-img" />
        </div>
        <!-- Franja azul -->
        <div class="blue-strip"></div>
        <!-- Títulos -->
        <h2 class="text-center">Inventarios y Producción</h2>
        <h3 class="text-center mb-4">Inicio de Sesión</h3>

        <form @submit.prevent="login">
          <div class="form-group">
            <div class="input-wrapper">
              <font-awesome-icon icon="user" class="input-icon" />
              <input
                type="text"
                v-model="usuario"
                class="form-control with-icon"
                placeholder="Usuario"
                required
              />
            </div>
          </div>
          <div class="form-group">
            <div class="input-wrapper">
              <font-awesome-icon icon="lock" class="input-icon" />
              <input
                :type="showPassword ? 'text' : 'password'"
                v-model="password"
                class="form-control with-icon"
                placeholder="Contraseña"
                required
              />
              <font-awesome-icon
                :icon="showPassword ? 'eye-slash' : 'eye'"
                class="toggle-password"
                @click="togglePassword"
              />
            </div>
          </div>
          <button type="submit" class="btn btn-primary w-100">
            <font-awesome-icon icon="sign-in-alt" /> Ingresar
          </button>
        </form>

        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import apiClient from "../services/axios";

export default {
  data() {
    return {
      usuario: '',
      password: '',
      errorMessage: '',
      showPassword: false,
    };
  },
  methods: {
    async login() {
      try {
        const response = await apiClient.post('/api/login', {
          usuario: this.usuario,
          password: this.password,
        });

        const { tipo_usuario, id, nombres, apellidos, token, message } = response.data;

        if (!token) {
          this.errorMessage = 'Token no recibido. Contacta al administrador.';
          console.error('Error: No se recibió un token en la respuesta del backend.');
          return;
        }

        localStorage.setItem('tipo_usuario', tipo_usuario);
        localStorage.setItem('usuario_id', id);
        localStorage.setItem('nombres', nombres);
        localStorage.setItem('apellidos', apellidos);
        localStorage.setItem('token', token);
        // console.log('DEBUG: Token almacenado:', token);

        alert(message); // Mostrar el mensaje dinámico del backend

        this.$emit('loginSuccess');

        if (tipo_usuario === 'admin') {
          this.$router.push('/menu');
        } else if (tipo_usuario === 'gerente') {
          this.$router.push('/menu-gerente');
        } else if (tipo_usuario === 'operador') {
          this.$router.push('/menu-operador');
        } else {
          this.errorMessage = 'Rol no reconocido. Contacta al administrador.';
        }
      } catch (error) {
        console.error('Error en el inicio de sesión:', error);
        if (error.response?.status === 403) {
          alert("Límite de sesiones alcanzado. Intenta más tarde.");
        } else if (error.response?.status === 409) {
          alert("Este usuario está inactivo. Contacta al administrador.");
        } else if (error.response?.status === 401) {
          this.errorMessage = "Credenciales incorrectas. Verifica tu usuario y contraseña.";
        } else {
          this.errorMessage =
            error.response?.data?.message || "Error al iniciar sesión. Por favor, inténtalo de nuevo.";
        }
      }
    },
    togglePassword() {
      this.showPassword = !this.showPassword;
    },
  },
};
</script>

<style scoped>
/* Contenedor principal */
#login {
  min-height: 100vh;
  display: flex;
  justify-content: center; /* Centrado horizontal */
  align-items: center; /* Centrado vertical */
  background-color: #ffffff; /* Fondo blanco */
}

/* Contenedor para centrar el formulario */
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100vh; /* Ocupa toda la altura de la pantalla */
}

/* Contenedor del formulario */
.login-container {
  max-width: 450px;
  width: 100%;
  padding: 40px 30px;
  background-color: #ffffff;
  border-radius: 10px;
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); /* Sombra más pronunciada */
  text-align: center;
}

/* Logo del cliente */
.logo-container {
  margin-bottom: 20px;
}

.logo-img {
  max-width: 200px; /* Ajusta según el tamaño real del logo */
  height: auto;
  display: block;
  margin: 0 auto; /* Centrado horizontal */
}

/* Franja azul */
.blue-strip {
  width: 100%;
  height: 4px;
  background-color: #007bff;
  margin-bottom: 20px;
}

/* Títulos */
h2 {
  font-size: 24px;
  color: #333;
  margin-bottom: 15px;
  font-weight: bold;
}

h3 {
  font-size: 18px;
  color: #555;
  margin-bottom: 25px;
  font-weight: normal;
}

/* Grupos de formulario */
.form-group {
  margin-bottom: 20px;
}

/* Contenedor para íconos dentro del input */
.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #666;
}

.form-control {
  width: 100%;
  padding: 12px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
  font-family: Arial, sans-serif;
  transition: border-color 0.3s;
}

.with-icon {
  padding-left: 35px;
}

.form-control:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 5px rgba(0, 123, 255, 0.5);
}

/* Ícono de mostrar/ocultar contraseña */
.toggle-password {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  cursor: pointer;
  color: #666;
}

/* Botón de inicio de sesión */
.btn {
  padding: 12px;
  font-size: 16px;
  font-weight: bold;
  border: none;
  border-radius: 5px;
  background-color: #007bff;
  color: #fff;
  cursor: pointer;
  width: 100%;
  transition: background-color 0.3s;
}

.btn:hover {
  background-color: #0056b3;
}

/* Mensaje de error */
.error-message {
  margin-top: 15px;
  color: #dc3545;
  font-size: 14px;
  font-weight: bold;
}

/* Responsividad */
@media (max-width: 576px) {
  .login-container {
    padding: 30px 20px;
    margin: 15px;
  }

  .logo-img {
    max-width: 150px;
  }

  h2 {
    font-size: 20px;
  }

  h3 {
    font-size: 16px;
  }
}
</style>