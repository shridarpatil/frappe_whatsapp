<template>
  <div class="h-screen w-80 bg-white shadow-md flex flex-col border-r border-gray-300">
    <div class="p-4 flex justify-between items-center border-b border-gray-300 bg-gray-100">
      <button @click="$router.go(-1)" class="text-3xl font-bold">←</button>
      <h2 class="text-lg font-semibold text-gray-700">Contacts</h2>
    </div>

    <div class="p-2 bg-gray-100">
      <input
        v-model="search"
        type="text"
        placeholder="Search contacts..."
        class="w-full p-2 rounded-md border border-gray-300 focus:outline-none focus:ring focus:ring-blue-300"
      />
    </div>

    <div class="flex-1 overflow-y-auto bg-gray-100">
      <ul v-if="filteredContacts.length">
        <li
          v-for="contact in filteredContacts"
          :key="contact.phone"
          class="flex items-center justify-between p-3 cursor-pointer transition duration-200 hover:bg-gray-300 border-b border-gray-300 bg-gray-100"
          :class="{ 'bg-blue-100': selectedContact === contact.phone }"
          @click="selectContact(contact)"
        >
          <div class="flex flex-col space-y-2 w-full">
            <div class="flex justify-between w-full">
              <div class="text-lg font-medium text-gray-800">{{ contact.phone }}</div>
              <Badge
                v-if="contact.unread_message_count > 0"
                variant="solid"
                theme="green"
                size="sm"
              >
                {{ contact.unread_message_count }}
              </Badge>
            </div>

            <div class="flex justify-between w-full">
              <div class="text-sm font-medium text-gray-800">{{ contact.whatsapp_name || "Unknown" }}</div>
              <div class="text-sm font-medium text-gray-400">{{ formatDate(contact.last_message_time) }}</div>
            </div>
          </div>
        </li>
      </ul>

      <div v-else-if="contacts.loading" class="text-gray-500 text-center p-4">Loading contacts...</div>
      <div v-else class="text-gray-500 text-center p-4">No contacts found</div>
    </div>
  </div>
</template>

<script>
import { Badge, createResource } from "frappe-ui";

export default {
  name: "WhatsappSidebar",
  data() {
    return {
      search: "",
      selectedContact: null,
    };
  },
  setup() {
    const contacts = createResource({
      url: "/api/method/frappe_whatsapp.api.whatsapp.get_whatsapp_contact",
      auto: true,
    });

    return { contacts };
  },
  computed: {
    filteredContacts() {
      return (this.contacts.data || []).filter(
        (contact) =>
          contact.phone.toLowerCase().includes(this.search.toLowerCase()) ||
          (contact.whatsapp_name || "").toLowerCase().includes(this.search.toLowerCase())
      );
    },
  },
  methods: {
    selectContact(contact) {
      this.selectedContact = contact.phone;
      this.$emit("contact-selected", { number: contact.phone, name: contact.whatsapp_name });
    },
    formatDate(dateString) {
      if (!dateString) return "N/A";
      const date = new Date(dateString);
      return date.toLocaleDateString();
    },
  },
};
</script>

<style scoped>
/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 10px;
}

/* Smooth transitions */
li {
  transition: background-color 0.2s ease-in-out;
}
</style>
