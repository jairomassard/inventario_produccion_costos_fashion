<template>
    <div id="admin-usuarios" class="container mt-5">
      <h1 class="text-center mb-4">Administración de Usuarios</h1>

      <div>
        <!-- Contenido de la página -->
        <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      </div>      
  
      <!-- Formulario para crear/editar usuario -->
      <div class="card mb-4 shadow-sm">
        <div class="card-body">
          <h2 class="card-title text-center">{{ usuarioActual.id ? 'Editar Usuario' : 'Crear Nuevo Usuario' }}</h2>
          <form @submit.prevent="guardarUsuario">
  
            <!-- Nombres y Apellidos -->
            <div class="row mb-3">
              <div class="col-md-6">
                <label for="nombres" class="form-label">Nombres:</label>
                <input type="text" v-model="usuarioActual.nombres" class="form-control" required>
              </div>
              <div class="col-md-6">
                <label for="apellidos" class="form-label">Apellidos:</label>
                <input type="text" v-model="usuarioActual.apellidos" class="form-control" required>
              </div>
            </div>
  
            <!-- Usuario, Contraseña, Tipo -->
            <div class="row mb-3">
              <div class="col-md-4">
                <label for="usuario" class="form-label">Usuario:</label>
                <input type="text" v-model="usuarioActual.usuario" class="form-control" required>
              </div>
              <div class="col-md-4">
                <label for="password" class="form-label">Contraseña:</label>
                <input type="password" v-model="usuarioActual.password" class="form-control" :required="!usuarioActual.id">
              </div>
              <div class="col-md-4">
                <label for="tipo_usuario" class="form-label">Tipo de Usuario:</label>
                <select v-model="usuarioActual.tipo_usuario" class="form-select" required>
                  <option value="admin">Administrador</option>
                  <option value="gerente">Gerente</option>
                  <option value="operador">Operador</option>
                </select>
              </div>
            </div>
  
            <!-- Celular y Correo -->
            <div class="row mb-3">
              <div class="col-md-6">
                <label for="celular" class="form-label">Celular:</label>
                <input type="text" v-model="usuarioActual.celular" class="form-control">
              </div>
              <div class="col-md-6">
                <label for="correo" class="form-label">Correo Electrónico:</label>
                <input type="email" v-model="usuarioActual.correo" class="form-control">
              </div>
            </div>
  
            <!-- Estado -->
            <div class="row mb-3">
              <div class="col-md-6">
                <label for="activo" class="form-label">Estado:</label>
                <select v-model="usuarioActual.activo" class="form-select">
                  <option :value="true">Activo</option>
                  <option :value="false">Inactivo</option>
                </select>
              </div>
            </div>
  
            <button type="submit" class="btn btn-primary w-100">{{ usuarioActual.id ? 'Actualizar' : 'Crear' }} Usuario</button>
          </form>
        </div>
      </div>
  
      <!-- Lista de Usuarios -->
      <h2 class="text-center mb-3">Lista de Usuarios</h2>
      <div v-if="usuarios.length" class="table-responsive">
        <table class="table table-striped table-hover">
          <thead class="table-dark">
            <tr>
              <th>ID</th>
              <th>Usuario</th>
              <th>Nombres</th>
              <th>Apellidos</th>
              <th>Celular</th>
              <th>Correo</th>
              <th>Tipo</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in usuarios" :key="user.id">
              <td>{{ user.id }}</td>
              <td>{{ user.usuario }}</td>
              <td>{{ user.nombres }}</td>
              <td>{{ user.apellidos }}</td>
              <td>{{ user.celular || 'N/A' }}</td>
              <td>{{ user.correo || 'N/A' }}</td>
              <td>{{ user.tipo_usuario }}</td>
              <td>
                <span :class="user.activo ? 'badge bg-success' : 'badge bg-danger'">
                  {{ user.activo ? 'Activo' : 'Inactivo' }}
                </span>
              </td>
              <td>
                <button class="btn btn-sm btn-info me-2" @click="editarUsuario(user)">Editar</button>
                <button class="btn btn-sm" :class="user.activo ? 'btn-danger' : 'btn-success'" @click="toggleEstado(user)">
                  {{ user.activo ? 'Desactivar' : 'Activar' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
  
  <script>
  import apiClient from '../services/axios'; // '@' apunta a la carpeta src en proyectos Vue.js configurados con Vite
  
  export default {
    data() {
      return {
        usuarios: [],
        usuarioActual: {
          id: null,
          usuario: '',
          password: '',
          nombres: '',
          apellidos: '',
          correo: '',
          celular: '',
          tipo_usuario: 'operador',
          activo: true
        }
      };
    },
    methods: {
      async consultarUsuarios() {
        try {
          const response = await apiClient.get('/api/usuarios');
          this.usuarios = response.data;
        } catch (error) {
          console.error("Error al obtener usuarios:", error);
        }
      },
      async guardarUsuario() {
        try {
            const url = this.usuarioActual.id ? '/api/usuarios' : '/api/usuarios';
            
            // Crear un objeto limpio para evitar enviar contraseñas vacías
            const usuarioParaGuardar = { ...this.usuarioActual };
            if (!usuarioParaGuardar.password) {
            delete usuarioParaGuardar.password; // Eliminar el campo si está vacío
            }

            await apiClient.post(url, usuarioParaGuardar); // Usar await para esperar la respuesta
            alert('Usuario guardado correctamente');
            this.consultarUsuarios(); // Refrescar la lista de usuarios
            this.resetFormulario(); // Limpiar el formulario
        } catch (error) {
            console.error("Error al guardar usuario:", error);
            alert('Ocurrió un error al guardar el usuario.');
        }
      },

      editarUsuario(user) {
        this.usuarioActual = { ...user, password: '' }; // Dejar el campo contraseña vacío para edición
      },
      async toggleEstado(user) {
        try {
          user.activo = !user.activo;
          await apiClient.post('/api/usuarios', user);
          this.consultarUsuarios();
        } catch (error) {
          console.error("Error al cambiar el estado del usuario:", error);
        }
      },
      resetFormulario() {
        this.usuarioActual = {
          id: null,
          usuario: '',
          password: '',
          nombres: '',
          apellidos: '',
          correo: '',
          celular: '',
          tipo_usuario: 'operador',
          activo: true
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
      this.consultarUsuarios();
    }
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
  
  
  