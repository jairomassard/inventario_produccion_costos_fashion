<template>
    <div>
      <h1>Gestión de Bodegas</h1>

      <div>
        <!-- Contenido de la página -->
        <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      </div>
  
      <!-- Formulario para Crear/Editar Bodega -->
      <form @submit.prevent="modoEdicion ? actualizarBodega() : crearBodega()">
        <div>
          <label for="nombre">Nombre de la Bodega:</label>
          <input v-model="bodega.nombre" id="nombre" required />
        </div>
        <div>
          <button v-if="!modoEdicion" type="submit">Crear Bodega</button>
          <div v-else>
            <button type="submit">Guardar Bodega</button>
            <button type="button" @click="cancelarEdicion">Cancelar</button>
          </div>
        </div>
      </form>
  
      <!-- Lista de Bodegas -->
      <div>
        <h2>Bodegas Creadas</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Nombre</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bod in bodegas" :key="bod.id">
              <td>{{ bod.id }}</td>
              <td>{{ bod.nombre }}</td>
              <td>
                <button @click="editarBodega(bod)">Editar</button>
                <button @click="eliminarBodega(bod.id)">Eliminar</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
  
  <script>
  import apiClient from '../services/axios';
  
  export default {
    name: 'BodegasForm',
    data() {
      return {
        bodega: {
          nombre: '',
        },
        bodegas: [],
        modoEdicion: false, // Determina si estamos editando una bodega
      };
    },
    methods: {
      async crearBodega() {
        try {
          await apiClient.post('/api/bodegas', this.bodega);
          alert('Bodega creada correctamente');
          this.cargarBodegas();
          this.resetearFormulario();
        } catch (error) {
          console.error('Error al crear bodega:', error);
        }
      },
      async cargarBodegas() {
        try {
          const response = await apiClient.get('/api/bodegas');
          this.bodegas = response.data;
        } catch (error) {
          console.error('Error al cargar bodegas:', error);
        }
      },
      editarBodega(bodega) {
        this.modoEdicion = true;
        this.bodega = { ...bodega }; // Copia los datos de la bodega al formulario
      },
      async actualizarBodega() {
        try {
          await apiClient.put(`/api/bodegas/${this.bodega.id}`, this.bodega);
          alert('Bodega actualizada correctamente');
          this.cargarBodegas();
          this.cancelarEdicion();
        } catch (error) {
          console.error('Error al actualizar bodega:', error);
        }
      },
      async eliminarBodega(id) {
        try {
          await apiClient.delete(`/api/bodegas/${id}`);
          alert('Bodega eliminada correctamente');
          this.cargarBodegas();
        } catch (error) {
          console.error('Error al eliminar bodega:', error);
        }
      },
      cancelarEdicion() {
        this.modoEdicion = false;
        this.resetearFormulario();
      },
      resetearFormulario() {
        this.bodega = {
          nombre: '',
        };
      },
      volverAlMenu() {
        const tipoUsuario = localStorage.getItem("tipo_usuario"); // Obtener el tipo de usuario del almacenamiento local

        if (tipoUsuario === "admin") {
          this.$router.push('/menu'); // Redirigir al menú del administrador
        } else if (tipoUsuario === "gerente") {
          this.$router.push('/menu-gerente'); // Redirigir al menú del gerente
        } else {
          alert("Rol no reconocido. Contacta al administrador."); // Manejo de error en caso de un rol desconocido
        }
      },
    },
    mounted() {
      this.cargarBodegas();
    },

  };
  </script>
  
  <style scoped>
  /* Contenedor principal */
  .produccion-admin {
    margin: 20px auto;
    max-width: 1200px;
    font-family: Arial, sans-serif;
    padding: 10px;
  }
  
  /* Títulos */
  h1 {
    text-align: center;
    color: #333;
    margin-bottom: 20px;
  }
  
  h2, h3 {
    color: #0056b3;
    margin-bottom: 15px;
  }
  
  /* Botones */
  button {
    padding: 0.6rem 1.2rem;
    border: none;
    background-color: #007bff;
    color: #fff;
    cursor: pointer;
    border-radius: 4px;
    font-size: 14px;
    margin-right: 10px;
  }
  
  button:hover {
    background-color: #0056b3;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.2);
  }
  
  /* Formularios */
  form label {
    font-weight: bold;
    display: block;
    margin-bottom: 5px;
    color: #555;
  }
  
  form input, form select {
    width: 100%;
    padding: 10px;
    margin-bottom: 15px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
  }
  
  /* Tablas */
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
    font-size: 14px;
  }
  
  th, td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
  }
  
  th {
    background-color: #f8f9fa;
    color: #333;
    font-weight: bold;
  }
  
  tbody tr:nth-child(odd) {
    background-color: #f9f9f9;
  }
  
  tbody tr:hover {
    background-color: #f1f1f1;
  }
  
  /* Secciones */
  section {
    margin-bottom: 30px;
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    background-color: #f8f9fa;
  }
  
  /* Historial de entregas */
  p {
    margin: 5px 0;
    color: #555;
    font-size: 14px;
  }
  
  /* --- Responsividad --- */
  @media (max-width: 768px) {
    /* Reducir márgenes en pantallas pequeñas */
    .produccion-admin {
      margin: 10px auto;
      padding: 10px;
    }
  
    /* Formularios en columna */
    form input, form select, button {
      width: 100%;
      margin-bottom: 10px;
      font-size: 16px;
    }
  
    /* Tablas desplazables horizontalmente */
    table {
      display: block;
      overflow-x: auto;
      white-space: nowrap;
    }
  
    th, td {
      font-size: 12px;
      padding: 8px;
    }
  
    /* Reducir tamaño de títulos */
    h1 {
      font-size: 20px;
    }
  
    h2, h3 {
      font-size: 18px;
    }
  }
  </style>