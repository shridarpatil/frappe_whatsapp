<script setup>
import { getCurrentInstance, ref, watch, nextTick, onMounted, onBeforeUnmount, computed, h } from 'vue';
import WhatsAppArea from './WhatsAppArea.vue';
import WhatsAppBox from './WhatsAppBox.vue';
import { createResource } from 'frappe-ui';
import WhatsAppIcon from './components/Icons/WhatsAppIcon.vue';
import WhatsappTemplateSelectorModal from './components/WhatsappTemplateSelectorModal.vue';
import WhatsappSidebar from './WhatsappSidebar.vue';
import WhatappAddToLeadModal from './components/WhatappAddToLeadModal.vue';
import {Button} from "frappe-ui"

const app = getCurrentInstance();
const { $socket } = app.appContext.config.globalProperties;

const props = defineProps({
  doctype: String,
  docname: String,
  phone: String,
  to: String,
  document: {
    type: Object,
    default: () => ({}) // Provide default structure
  }
});

const selectedPhone = ref('');
const showWhatsappTemplates = ref(false);
const showAddLeadModal = ref(false);


function updatePhoneNumber(newPhone, newName) {
  selectedPhone.value = newPhone;
}

function sendTemplate(template) {
  showWhatsappTemplates.value = false;
  try {
    createResource({
      url: "",
      params: {
        reference_doctype: props.doctype,
        reference_name: props.docname,
        to: props.phone,
        template,
      },
      auto: true,
      headers: {
        'X-Frappe-CSRF-Token': frappe.csrf_token
      }
    }).then(() => {
      console.log('Template sent successfully!');
    });
  } catch (error) {
    console.error('Error sending template:', error);
  }
}

const whatsappMessages = computed(() =>
  createResource({
    url: '',
    cache: ['whatsapp_messages', selectedPhone.value],
    params: {
      phone: selectedPhone.value || ""
    },
    auto: true,
    transform: (data) => data.sort((a, b) => new Date(a.creation) - new Date(b.creation)),
  })
);

function scrollToBottom() {
  nextTick(() => {
    const el = document.querySelector('.messages-container');
    if (el) el.scrollTop = el.scrollHeight;
  });
}

watch(whatsappMessages.value.data, scrollToBottom);

// WebSocket updates
onMounted(() => {
  $socket.on('whatsapp_message', (data) => {
    if (
      (data.reference_doctype === props.doctype && data.reference_name === props.docname) ||
      data.from === selectedPhone.value ||
      data.to === selectedPhone.value
    ) {
      whatsappMessages.value.reload();
    }
  });
});

onBeforeUnmount(() => {
  $socket.off('whatsapp_message');
});
</script>

<template>
  <div class="flex h-full">
    <div class="w-1/5">
      <WhatsappSidebar @contact-selected="updatePhoneNumber" />
    </div>

    <div class="whatsapp-chat-container w-full flex-col">
      <div class="top-bar flex items-center justify-between p-3 bg-white shadow">
        <div class="flex flex-col">
          <h2 class="text-xl font-semibold text-gray-800">{{ selectedPhone.number || '' }}</h2>
          <h2 class="text-md font-semibold text-gray-800">{{ selectedPhone.name || '' }}</h2>
        </div>
        <div class="flex items-center space-x-4">
          <Button
    :variant="'solid'"
    :ref_for="true"
    theme="gray"
    size="sm"
    label="Button"
    :loading="false"
    :loadingText="null"
    :disabled="false"
    :link="null"
    @click="showAddLeadModal = true"
  >
            + Add Lead
          </button>
          
          <Button
              :variant="'subtle'"
              :ref_for="true"
              theme="gray"
              size="sm"
              label="Button"
              :loading="false"
              :loadingText="null"
              :disabled="false"
              :link="null"
              >
            Send Template
          </Button>
        </div>
      </div>
      
      <div
  v-if="!selectedPhone"
  class="flex flex-1 flex-col items-center justify-center gap-3 text-xl font-medium text-gray-500"
>
  <!-- <WhatsAppIcon class="h-10 w-10 text-gray-500" /> -->
  <span>Click Any Contact To View Conversation</span>
</div>

<div
  v-else-if="selectedPhone && !whatsappMessages.data?.length"
  class="flex flex-1 flex-col items-center justify-center gap-3 text-xl font-medium text-gray-500"
>
  <WhatsAppIcon class="h-10 w-10 text-gray-500" />
  <span>No messages yet</span>
</div>

<div v-else class="messages-container flex-1 p-4 overflow-y-auto">
  <WhatsAppArea class="px-3 sm:px-10" v-model:reply="reply" :messages="whatsappMessages.data" />
</div>


      <div class="chat-box-container border-t">
        <WhatsAppBox
          ref="whatsappBox"
          v-model:doc="props.document"
          v-model:reply="reply"
          :doctype="props.doctype"
          :docname="props.docname"
          :phone="props.phone"
          @message-sent="whatsappMessages.reload"
        />
      </div>

      <WhatsappTemplateSelectorModal
        v-if="whatsappEnabled"
        v-model="showWhatsappTemplates"
        :doctype="doctype"
        @send="(t) => sendTemplate(t)"
      />

      <WhatappAddToLeadModal 
        v-model="showAddLeadModal" 
        :leadData="{
        first_name: selectedPhone.name || '',
        contact_number: selectedPhone.number|| ''
        }" 
        />

    </div>
  </div>
</template>

<style>
.whatsapp-chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh);
  max-height: 100%;
  background-color: #f0f2f5;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e0e0e0;
}

.send-template-btn {
  background-color: #bababa;
  padding: 6px 14px;
  border-radius: 6px;
  transition: background-color 0.3s ease;
}

.send-template-btn:hover {
  background-color: #999999;
}

.messages-container {
  overflow-y: auto;
}
</style>
