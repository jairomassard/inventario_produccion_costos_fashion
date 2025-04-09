<template> 
  <div class="menu-principal">
    <div class="header-image">
      <img src="/images/cabezote.jpg" alt="Cabezote" class="img-fluid w-100" />
    </div>
    <br/>
    <h1>Menú Principal</h1>
    <br/>
    <div class="menu-grid">
      <!--<router-link class="menu-button" to="/productos">Productos</router-link>-->
      <router-link class="menu-button" to="/cargar-cantidades">Cargar Compras</router-link>
      <router-link class="menu-button" to="/cargar-ventas">Cargar Ventas</router-link>
      <router-link class="menu-button" to="/cargar-notas-credito">Cargar Devoluciones</router-link>
      <router-link class="menu-button" to="/bodegas">Bodegas</router-link>
      <router-link class="menu-button" to="/trasladar-cantidades">Trasladar Cantidades</router-link>
      <router-link class="menu-button" to="/consulta-inventario">Consultar Inventario</router-link>
      <router-link class="menu-button" to="/kardex">Kardex</router-link>
      <!--<router-link class="menu-button" to="/modulo-materiales">Gestión de Materiales</router-link>-->
      <router-link class="menu-button" to="/produccion-admin" v-if="tipoUsuario === 'admin'">Gestión de Producción</router-link>
      <router-link class="menu-button" to="/reportes-produccion" v-if="tipoUsuario === 'admin'">Reportes de Producción</router-link>
      <router-link class="menu-button" to="/gestion-productos-materiales" v-if="tipoUsuario === 'admin'">Gestión Productos y Materiales</router-link>
      <router-link class="menu-button" to="/ajuste-inventario" v-if="tipoUsuario === 'admin'">Ajuste de Inventario</router-link>
      <router-link class="menu-button" to="/admin-usuarios" v-if="tipoUsuario === 'admin'">Administración de Usuarios</router-link>
      
      
    </div>
    <button @click="cerrarSesion" class="btn btn-danger cerrar-sesion">Cerrar Sesión</button>
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

.menu-principal {
  max-width: 800px;
  margin: 0 auto;
  text-align: center;
  font-family: Arial, sans-serif;
}

.menu-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* Tres columnas */
  gap: 20px; /* Espaciado entre los botones */
  max-width: 900px; /* Ancho máximo del contenedor */
  margin: 0 auto; /* Centrar la cuadrícula */
  text-align: center;
}

.menu-button {
  display: block;
  padding: 1rem;
  text-decoration: none;
  background-color: #007bff;
  color: white;
  text-align: center;
  border-radius: 8px;
  font-weight: bold;
  transition: background-color 0.3s ease, transform 0.2s ease;
}

.menu-button:hover {
  background-color: #0056b3;
  transform: translateY(-2px);
}

.cerrar-sesion {
  display: block;
  margin: 20px auto;
  padding: 10px 20px;
  background-color: #dc3545;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.cerrar-sesion:hover {
  background-color: #c82333;
}
</style>

