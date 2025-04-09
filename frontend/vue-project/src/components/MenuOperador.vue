<template>
    <div class="header-image">
      <img src="/images/cabezote.jpg" alt="Cabezote" class="img-fluid w-100" />
    </div>
    <br/>

  <div class="menu-operador">



    <h1>Menú</h1>

    <ul class="menu-list">
      <li>
        <router-link to="/consulta-inventarioOperador" class="menu-link">
          Consultar Inventario
        </router-link>
      </li>
      <li>
        <router-link to="/produccion-operador" class="menu-link">
          Gestión de Producción
        </router-link>
      </li>
      <li>
        <router-link
          to="/reportes-produccion-operador"
          v-if="tipoUsuario === 'operador'"
          class="menu-button menu-link"
        >
          Reportes de Producción
        </router-link>

      </li>  

    </ul>
    <button @click="cerrarSesion" class="btn btn-danger">Cerrar Sesión</button>
  </div>
</template>

<script>
import apiClient from '../services/axios';

export default {
  data() {
    return {
      tipoUsuario: localStorage.getItem("tipo_usuario"),
    };
  },
  
  methods: {
    async cerrarSesion() {
      try {
        const token = localStorage.getItem("token");
        if (token) {
          await apiClient.post("/api/logout", {}, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });
        }
      } catch (error) {
        console.error("Error al cerrar sesión:", error.response?.data || error.message);
      } finally {
        // Limpiar almacenamiento local y redirigir al usuario
        localStorage.clear();
        this.$router.push("/");
      }
    },
  
  },
};
</script>

<style scoped>
/* Imagen de encabezado */
.header-image img {
  width: 100%;
  height: auto;
  border-bottom: 4px solid #007bff; /* Barra decorativa */
}

/* Contenedor del menú */
.menu-operador {
  max-width: 600px;
  margin: 0 auto;
  text-align: center;
  font-family: Arial, sans-serif;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 10px;
  box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
}

/* Títulos */
h1 {
  font-size: 24px;
  margin-bottom: 20px;
  color: #0056b3;
}

/* Lista de enlaces */
.menu-list {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
}

.menu-list li {
  margin-bottom: 15px;
}

/* Enlaces */
.menu-link {
  text-decoration: none;
  font-size: 18px;
  color: #007bff;
  background-color: #e9ecef;
  padding: 10px 20px;
  border-radius: 6px;
  display: inline-block;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.menu-link:hover {
  background-color: #007bff;
  color: #fff;
}

/* Botón */
button {
  padding: 10px 20px;
  border: none;
  background-color: #dc3545;
  color: #fff;
  cursor: pointer;
  border-radius: 6px;
  font-size: 16px;
  transition: background-color 0.3s ease;
}

button:hover {
  background-color: #bd2130;
}
</style>
