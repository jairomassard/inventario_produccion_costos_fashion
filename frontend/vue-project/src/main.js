import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// Importar FontAwesome
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { library } from '@fortawesome/fontawesome-svg-core'
import { fas } from '@fortawesome/free-solid-svg-icons'

// Agregar íconos a la librería
library.add(fas)

// Filtrar mensajes de error específicos en la consola
// const originalConsoleError = console.error;
// console.error = (...args) => {
//   if (args[0]?.includes('runtime.lastError')) {
//     return; // Ignora el mensaje "Unchecked runtime.lastError"
//   }
//   originalConsoleError.apply(console, args);
//};

const app = createApp(App)

// Registrar FontAwesome como componente global
app.component('font-awesome-icon', FontAwesomeIcon)

app.use(createPinia())
app.use(router)

app.mount('#app')
