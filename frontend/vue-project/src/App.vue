<template>
  <div>
    <router-view />
  </div>
</template>

<script>
export default {
  mounted() {
    window.addEventListener('beforeunload', this.limpiarSesion);
  },
  methods: {
    async limpiarSesion() {
        const token = localStorage.getItem('token');
        if (token) {
            try {
                await axios.post('/api/logout', null, {
                  headers: { Authorization: `Bearer ${token}` },
                });
            } catch (error) {
                console.error('Error al cerrar sesión automáticamente:', error);
            }
        }
        localStorage.clear();
    },
  },
  beforeDestroy() {
    window.removeEventListener('beforeunload', this.limpiarSesion);
  },
  name: "App",
};
</script>



