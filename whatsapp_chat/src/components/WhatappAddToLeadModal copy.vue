<template>
  <Dialog v-model="show" :options="{ title: 'Add Lead', size: '2xl' }">
    <template #body-content>
      <form @submit.prevent="submitLead">
        <div class="p-2">
          <FormControl
            type="text"
            size="sm"
            variant="subtle"
            placeholder="First Name"
            label="First Name"
            v-model="lead.first_name"
          />
        </div>

        <!-- Executive Dropdown -->
        <div class="p-2 text-black">
          <FormControl
            type="select"
            :options="executiveOptions"
            size="sm"
            variant="subtle"
            placeholder="Select Executive"
            label="Executive"
            v-model="lead.executive"
          />
        </div>

        <!-- Center Dropdown -->
        <div class="p-2 text-black">
          <FormControl
            type="select"
            :options="centerOptions"
            size="sm"
            variant="subtle"
            placeholder="Select Center"
            label="Center"
            v-model="lead.center"
          />
        </div>

        <div class="p-2">
          <FormControl
            type="text"
            size="sm"
            variant="subtle"
            placeholder="City Name"
            label="City Name"
            v-model="lead.city"
          />
        </div>

        <div class="p-2">
          <FormControl
            type="text"
            size="sm"
            variant="subtle"
            placeholder="Source"
            label="Source"
            v-model="lead.source"
            disabled
          />
        </div>

        <div class="p-2">
          <FormControl
            type="text"
            size="sm"
            variant="subtle"
            placeholder="Contact Number"
            label="Contact Number"
            v-model="lead.contact_number"
          />
        </div>

        <div class="mt-4 flex justify-end text-black">
          <Button label="Cancel" class="mr-2" @click="show = false" />
          <Button
            variant="solid"
            theme="gray"
            size="sm"
            label="Save Lead"
            @click="submitLead"
          />
        </div>
      </form>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, defineProps, defineModel, watchEffect } from 'vue'
import { Button, FormControl, createResource } from 'frappe-ui'

const show = defineModel()

const formDataResource = createResource({
  url: 'frappe_whatsapp.api.whatsapp.get_form_data',
  auto: true
})

const executiveOptions = ref([])
const centerOptions = ref([])

watchEffect(() => {
  if (formDataResource.data) {
    console.log('Fetched Data:', formDataResource.data)

    if (formDataResource.data.executive) {
      executiveOptions.value = formDataResource.data.executive.map(exec => ({
        label: exec.fullname,
        value: exec.fullname
      }))
    }

    if (formDataResource.data.center) {
      centerOptions.value = formDataResource.data.center.map(center => ({
        label: center.name,
        value: center.name
      }))
    }
  }
})

const props = defineProps({
  leadData: {
    type: Object,
    default: () => ({})
  }
})

const lead = ref({
  first_name: '',
  executive: '',
  center: '',
  city: 'Pune',
  source: 'Whatsapp',
  contact_number: ''
})

watchEffect(() => {
  if (props.leadData) {
    lead.value.first_name = props.leadData.first_name || ''
    lead.value.contact_number = props.leadData.contact_number || ''
  }
})

const submitLead = () => {
  console.log('Submitting Lead:', lead.value)
  show.value = false
}
</script>
