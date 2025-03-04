<script setup>
import { ref, reactive, onMounted } from 'vue';
import WhatsApp from './Whatsapp.vue'; // Rendering Component

// non-supportive translation fn.
window.__ = (text) => text;

const doctype = ref('');
const docname = ref('');
const phone = ref('');
const whatsapp = ref(null);
const documentData = reactive({
  data: {}, // Initialize with an empty object
});
const loading = ref(true);
const error = ref('');

// Helper: Extract query parameters from URL
function getQueryParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    doctype: "Lead" || '',
    docname: 'sandip%20pandit'|| '',
    phone: '919558065644' || '',
  };
}

// Check and fetch `doctype` and `docname` from either DOM or URL
function checkAndFetch() {
  const leadWhatsAppTab = document.querySelector('#lead-whatsapp_tab');

  if (leadWhatsAppTab) {
    console.log('Lead WhatsApp tab found.');
    const doc = typeof cur_frm !== 'undefined' ? cur_frm : null;
    if (doc?.doctype && doc?.docname) {
      doctype.value = doc.doctype;
      docname.value = doc.docname;
      documentData.data = doc.doc;
      phone.value = doc.doc.contact_number.replace(/\D/g, "");
      loading.value = false;
    } else {
      error.value = 'Lead WhatsApp details not found.';
      loading.value = false;
    }
  } else {
    // Use URL query parameters
    const queryParams = getQueryParams();
    phone.value = queryParams.phone || '';
    
    if (queryParams.doctype && queryParams.docname) {
      doctype.value = queryParams.doctype;
      docname.value = queryParams.docname;
      loading.value = false;
    } else {
      error.value = 'Doctype and Docname missing from URL.';
      loading.value = false;
    }
  }
}

// On mount, check and fetch
onMounted(() => {
  checkAndFetch();
});
</script>

<template>
  <div v-if="loading" class="flex items-center justify-center h-full">
    <span>Loading...</span>
  </div>
  <div v-else-if="error" class="text-red-500 text-center">
    {{ error }}
  </div>
  <WhatsApp
    v-else
    ref="whatsapp"
    :doctype="doctype"
    :docname="docname"
    :phone="phone"
    :to="documentData.data.contact_number"
    :document="documentData.data"
  />
</template>
